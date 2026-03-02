"""
屏幕截取模块
============
支持两种截取方式 (自动选择):

1. **PrintWindow API** (首选)
   直接从 VRChat 窗口缓冲区取图，即使窗口被其他窗口完全遮挡
   也能正确截取游戏画面。用户可以正常使用电脑做其他事。

2. **mss 屏幕截取** (回退)
   如果 PrintWindow 对 VRChat 不可用 (极少数情况)，
   回退到截取屏幕上窗口区域的像素，此时需要保持 VRChat 窗口可见。

首次调用 grab_window() 时会自动测试 PrintWindow 是否可用，
并在日志中提示结果。

注意: mss 实例是线程本地的，不能跨线程使用。
PrintWindow 基于 ctypes + GDI，天然线程安全。
"""

import os
import threading
import ctypes
import ctypes.wintypes
import cv2
import numpy as np
from mss import mss

import config
from utils.logger import log


# ═══════════════════ Win32 GDI 常量 & 函数 ═══════════════════

user32 = ctypes.windll.user32
gdi32  = ctypes.windll.gdi32

PW_CLIENTONLY          = 0x1      # 只截取客户区（不含标题栏/边框）
PW_RENDERFULLCONTENT   = 0x2      # 使用 DWM 合成渲染（Win8.1+，支持 DirectX）
SRCCOPY                = 0x00CC0020
BI_RGB                 = 0
DIB_RGB_COLORS         = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize',          ctypes.c_uint32),
        ('biWidth',         ctypes.c_int32),
        ('biHeight',        ctypes.c_int32),
        ('biPlanes',        ctypes.c_uint16),
        ('biBitCount',      ctypes.c_uint16),
        ('biCompression',   ctypes.c_uint32),
        ('biSizeImage',     ctypes.c_uint32),
        ('biXPelsPerMeter', ctypes.c_int32),
        ('biYPelsPerMeter', ctypes.c_int32),
        ('biClrUsed',       ctypes.c_uint32),
        ('biClrImportant',  ctypes.c_uint32),
    ]


# ═══════════════════ 截取器 ═══════════════════

class ScreenCapture:
    """高速屏幕截取器（线程安全）"""

    def __init__(self):
        self._local = threading.local()   # 每个线程独立的 mss 实例
        self.screen_w = 0
        self.screen_h = 0

        # PrintWindow 可用性（首次 grab_window 时自动检测）
        # None=未测试, True=可用, False=不可用
        self._use_printwindow = None
        self._pw_tested_hwnd = None        # 记录测试时的 HWND

        # 主线程中获取屏幕尺寸
        sct = self._get_sct()
        primary = sct.monitors[1]
        self.screen_w = primary["width"]
        self.screen_h = primary["height"]

        # 确保 debug 目录存在
        os.makedirs(config.DEBUG_DIR, exist_ok=True)

    def _get_sct(self):
        """获取当前线程的 mss 实例（延迟初始化）"""
        if not hasattr(self._local, "sct") or self._local.sct is None:
            self._local.sct = mss()
        return self._local.sct

    def _release_printwindow_ctx(self):
        """释放当前线程缓存的 PrintWindow GDI 资源。"""
        ctx = getattr(self._local, "pw_ctx", None)
        if not ctx:
            return
        try:
            if ctx.get("mDC") and ctx.get("old_bmp"):
                gdi32.SelectObject(ctx["mDC"], ctx["old_bmp"])
            if ctx.get("bmp"):
                gdi32.DeleteObject(ctx["bmp"])
            if ctx.get("mDC"):
                gdi32.DeleteDC(ctx["mDC"])
        except Exception:
            pass
        self._local.pw_ctx = None

    def _ensure_printwindow_ctx(self, hwnd, w, h):
        """确保当前线程存在匹配尺寸的 PrintWindow 缓存上下文。"""
        ctx = getattr(self._local, "pw_ctx", None)
        if (ctx and ctx.get("hwnd") == hwnd and ctx.get("w") == w
                and ctx.get("h") == h and ctx.get("mDC") and ctx.get("bmp")):
            return ctx

        self._release_printwindow_ctx()

        wDC = user32.GetDC(hwnd)
        if not wDC:
            return None

        mDC = None
        bmp = None
        old_bmp = None
        try:
            mDC = gdi32.CreateCompatibleDC(wDC)
            if not mDC:
                return None
            bmp = gdi32.CreateCompatibleBitmap(wDC, w, h)
            if not bmp:
                return None
            old_bmp = gdi32.SelectObject(mDC, bmp)

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = BI_RGB

            buf = ctypes.create_string_buffer(w * h * 4)
            ctx = {
                "hwnd": hwnd,
                "w": w,
                "h": h,
                "mDC": mDC,
                "bmp": bmp,
                "old_bmp": old_bmp,
                "bmi": bmi,
                "buf": buf,
            }
            self._local.pw_ctx = ctx
            return ctx
        finally:
            user32.ReleaseDC(hwnd, wDC)
            # 创建失败时清理临时资源
            if (getattr(self._local, "pw_ctx", None) is None):
                try:
                    if mDC and old_bmp:
                        gdi32.SelectObject(mDC, old_bmp)
                    if bmp:
                        gdi32.DeleteObject(bmp)
                    if mDC:
                        gdi32.DeleteDC(mDC)
                except Exception:
                    pass

    # ────────────────── PrintWindow 截取 ──────────────────

    def _grab_printwindow(self, hwnd):
        """
        使用 PrintWindow API 截取窗口客户区内容。

        原理:
          PrintWindow 向目标窗口发送 WM_PRINT 消息，
          窗口将自身客户区内容渲染到我们提供的内存 DC 上。
          PW_RENDERFULLCONTENT 标志让 DWM 使用合成渲染，
          可以正确捕获 DirectX/OpenGL 窗口内容（如 Unity/VRChat）。

        Returns:
            BGR numpy 数组 或 None（失败时）
        """
        if not hwnd:
            return None

        wDC = None
        try:
            rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            w = rect.right
            h = rect.bottom
            if w <= 0 or h <= 0:
                return None

            ctx = self._ensure_printwindow_ctx(hwnd, w, h)
            if not ctx:
                return None

            mDC = ctx["mDC"]
            bmp = ctx["bmp"]
            ok = user32.PrintWindow(
                hwnd, mDC,
                PW_CLIENTONLY | PW_RENDERFULLCONTENT
            )

            if not ok:
                wDC = user32.GetDC(hwnd)
                if wDC:
                    gdi32.BitBlt(mDC, 0, 0, w, h, wDC, 0, 0, SRCCOPY)

            gdi32.GetDIBits(
                mDC, bmp, 0, h,
                ctx["buf"], ctypes.byref(ctx["bmi"]), DIB_RGB_COLORS
            )

            img = np.frombuffer(ctx["buf"], dtype=np.uint8).reshape((h, w, 4))
            return img[:, :, :3].copy()

        except Exception as e:
            self._release_printwindow_ctx()
            log.debug(f"PrintWindow 异常: {e}")
            return None
        finally:
            if wDC:
                user32.ReleaseDC(hwnd, wDC)

    def _test_printwindow(self, hwnd) -> bool:
        """
        测试 PrintWindow 是否对当前窗口可用。
        截取一帧，检查是否为全黑（全黑 = 不可用）。
        """
        img = self._grab_printwindow(hwnd)
        if img is None:
            return False

        # 检查是否为全黑图像（DirectX 独占模式会返回全黑）
        mean_val = float(np.mean(img))
        if mean_val > 5.0:
            h, w = img.shape[:2]
            log.info(
                f"✓ PrintWindow 可用 ({w}×{h}, 亮度={mean_val:.1f}) "
                f"— VRChat 被遮挡也能正确截图"
            )
            return True
        else:
            log.warning(
                f"✗ PrintWindow 返回黑屏 (亮度={mean_val:.1f}) "
                f"— 请保持 VRChat 窗口不被遮挡!"
            )
            return False

    # ────────────────── mss 截取 (回退) ──────────────────

    def grab(self, region=None):
        """
        截取屏幕。
        Args:
            region: (x, y, w, h) 或 None=全屏
        Returns:
            BGR numpy 数组
        """
        sct = self._get_sct()

        if region:
            mon = {
                "left":   int(region[0]),
                "top":    int(region[1]),
                "width":  max(1, int(region[2])),
                "height": max(1, int(region[3])),
            }
        else:
            mon = sct.monitors[1]

        raw = np.array(sct.grab(mon))
        return raw[:, :, :3].copy()

    # ────────────────── 主接口 ──────────────────

    def grab_window(self, window_mgr):
        """
        截取 VRChat 窗口的客户区。

        自动选择最佳截取方式:
        1. PrintWindow — 窗口可被其他窗口遮挡 (首选)
        2. mss — 截取屏幕区域 (回退, 需要窗口可见)

        Returns:
            (image, region)  — region 为 (x, y, w, h) 或 None
        """
        hwnd = window_mgr.hwnd if window_mgr.is_valid() else None

        # ── 首次调用 / HWND 变更: 测试 PrintWindow 是否可用 ──
        if hwnd and (self._use_printwindow is None
                     or self._pw_tested_hwnd != hwnd):
            self._pw_tested_hwnd = hwnd
            self._use_printwindow = self._test_printwindow(hwnd)

        # ── 方式1: PrintWindow (直接窗口截取) ──
        if self._use_printwindow and hwnd:
            img = self._grab_printwindow(hwnd)
            if img is not None:
                # 快速检查: 确保不是意外的全黑帧
                # （窗口最小化等极端情况可能返回黑屏）
                if np.mean(img) > 2.0:
                    return img, None

        # ── 方式2: mss 屏幕截取 (回退) ──
        region = window_mgr.get_region()
        if region and region[2] > 0 and region[3] > 0:
            return self.grab(region), region

        # 最后回退: 全屏
        return self.grab(), None

    # ────────────────── 工具方法 ──────────────────

    def save_debug(self, image, name: str = "screenshot"):
        """保存调试截图到 debug/ 目录"""
        path = os.path.join(config.DEBUG_DIR, f"{name}.png")
        cv2.imwrite(path, image)
        log.debug(f"调试截图已保存: {path}")

    def reset_capture_method(self):
        """
        重置截取方式检测。
        当 VRChat 窗口重启或切换模式时调用，强制重新测试。
        """
        self._use_printwindow = None
        self._pw_tested_hwnd = None
        self._release_printwindow_ctx()
        log.info("截取方式已重置，下次截图时将重新检测")
