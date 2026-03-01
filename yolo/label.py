"""
YOLO 标注辅助工具
================
用 OpenCV 窗口打开未标注的截图，让用户画框 + 选择类别。
标注结果保存为 YOLO 格式 (.txt)，完成后自动移到 train/ 目录。

类别:
  0 = fish  (鱼图标)
  1 = bar   (白色捕捉条)
  2 = track (钓鱼轨道)

操作:
  鼠标拖拽  = 画框
  1/2/3     = 设置类别 (fish/bar/track)
  Z         = 撤销上一个框
  S / Enter = 保存并下一张
  D         = 删除当前图片 (跳过)
  Q / Esc   = 退出

用法:
    python -m yolo.label
    python -m yolo.label --split 0.2   # 20% 分到 val/
"""

import os
import sys
import random
import shutil
import argparse
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

BASE = os.path.join(config.BASE_DIR, "yolo", "dataset")
UNLABELED = os.path.join(BASE, "images", "unlabeled")
TRAIN_IMG = os.path.join(BASE, "images", "train")
TRAIN_LBL = os.path.join(BASE, "labels", "train")
VAL_IMG = os.path.join(BASE, "images", "val")
VAL_LBL = os.path.join(BASE, "labels", "val")

CLASS_NAMES = {0: "fish", 1: "bar", 2: "track"}
CLASS_COLORS = {0: (0, 255, 0), 1: (255, 255, 255), 2: (255, 100, 0)}

drawing = False
ix, iy = 0, 0
boxes = []          # [(class_id, x1, y1, x2, y2), ...]
current_class = 0
img_display = None
img_orig = None


def draw_overlay():
    global img_display
    img_display = img_orig.copy()
    h, w = img_display.shape[:2]

    for cls, x1, y1, x2, y2 in boxes:
        color = CLASS_COLORS.get(cls, (128, 128, 128))
        cv2.rectangle(img_display, (x1, y1), (x2, y2), color, 2)
        label = f"{CLASS_NAMES.get(cls, '?')} ({cls})"
        cv2.putText(img_display, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    info = (f"Class: {current_class}={CLASS_NAMES.get(current_class, '?')} | "
            f"Boxes: {len(boxes)} | "
            f"[1]fish [2]bar [3]track [Z]undo [S]save [D]skip [Q]quit")
    cv2.putText(img_display, info, (5, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)


def mouse_cb(event, x, y, flags, param):
    global drawing, ix, iy, img_display

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        tmp = img_display.copy()
        color = CLASS_COLORS.get(current_class, (128, 128, 128))
        cv2.rectangle(tmp, (ix, iy), (x, y), color, 2)
        cv2.imshow("Label Tool", tmp)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, y1 = min(ix, x), min(iy, y)
        x2, y2 = max(ix, x), max(iy, y)
        if x2 - x1 > 5 and y2 - y1 > 5:
            boxes.append((current_class, x1, y1, x2, y2))
            draw_overlay()
            cv2.imshow("Label Tool", img_display)


def save_annotation(img_path, dst_img_dir, dst_lbl_dir):
    """保存 YOLO 格式标注并移动图片"""
    h, w = img_orig.shape[:2]
    name = os.path.splitext(os.path.basename(img_path))[0]

    lbl_path = os.path.join(dst_lbl_dir, name + ".txt")
    with open(lbl_path, "w") as f:
        for cls, x1, y1, x2, y2 in boxes:
            cx = ((x1 + x2) / 2) / w
            cy = ((y1 + y2) / 2) / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            f.write(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

    dst_path = os.path.join(dst_img_dir, os.path.basename(img_path))
    shutil.move(img_path, dst_path)
    return lbl_path, dst_path


def main():
    global current_class, boxes, img_orig, img_display

    parser = argparse.ArgumentParser(description="YOLO 标注工具")
    parser.add_argument("--split", type=float, default=0.2,
                        help="验证集比例 (默认 0.2)")
    args = parser.parse_args()

    os.makedirs(TRAIN_IMG, exist_ok=True)
    os.makedirs(TRAIN_LBL, exist_ok=True)
    os.makedirs(VAL_IMG, exist_ok=True)
    os.makedirs(VAL_LBL, exist_ok=True)

    files = sorted([
        f for f in os.listdir(UNLABELED)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))
    ])

    if not files:
        print(f"[提示] {UNLABELED} 中没有未标注的图片")
        print("  先运行: python -m yolo.collect")
        return

    print(f"[✓] 找到 {len(files)} 张未标注图片")
    print(f"[设置] 验证集比例: {args.split:.0%}")
    print()

    cv2.namedWindow("Label Tool", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Label Tool", mouse_cb)

    labeled = 0
    for i, fname in enumerate(files):
        fpath = os.path.join(UNLABELED, fname)
        img_orig = cv2.imread(fpath)
        if img_orig is None:
            continue

        boxes = []
        current_class = 0

        h, w = img_orig.shape[:2]
        dw = min(w, 1280)
        dh = int(h * dw / w)
        cv2.resizeWindow("Label Tool", dw, dh)

        draw_overlay()
        cv2.imshow("Label Tool", img_display)
        title = f"[{i+1}/{len(files)}] {fname} ({w}x{h})"
        print(f"  {title}")

        while True:
            key = cv2.waitKey(0) & 0xFF

            if key == ord("1"):
                current_class = 0
                print(f"    类别 → fish (0)")
                draw_overlay()
                cv2.imshow("Label Tool", img_display)
            elif key == ord("2"):
                current_class = 1
                print(f"    类别 → bar (1)")
                draw_overlay()
                cv2.imshow("Label Tool", img_display)
            elif key == ord("3"):
                current_class = 2
                print(f"    类别 → track (2)")
                draw_overlay()
                cv2.imshow("Label Tool", img_display)
            elif key == ord("z") or key == ord("Z"):
                if boxes:
                    removed = boxes.pop()
                    print(f"    撤销: {CLASS_NAMES.get(removed[0], '?')}")
                    draw_overlay()
                    cv2.imshow("Label Tool", img_display)
            elif key == ord("s") or key == ord("S") or key == 13:  # Enter
                if not boxes:
                    print("    [跳过] 没有标注框")
                    break
                is_val = random.random() < args.split
                d_img = VAL_IMG if is_val else TRAIN_IMG
                d_lbl = VAL_LBL if is_val else TRAIN_LBL
                lbl, dst = save_annotation(fpath, d_img, d_lbl)
                split_name = "val" if is_val else "train"
                print(f"    [保存] {len(boxes)} 个框 → {split_name}/")
                labeled += 1
                break
            elif key == ord("d") or key == ord("D"):
                print("    [删除] 跳过此图")
                break
            elif key == ord("q") or key == ord("Q") or key == 27:  # Esc
                print(f"\n[退出] 共标注 {labeled} 张")
                cv2.destroyAllWindows()
                return

    cv2.destroyAllWindows()
    print(f"\n[完成] 共标注 {labeled} 张图片")
    print(f"  训练集: {TRAIN_IMG}")
    print(f"  验证集: {VAL_IMG}")
    print(f"\n下一步: python -m yolo.train")


if __name__ == "__main__":
    main()
