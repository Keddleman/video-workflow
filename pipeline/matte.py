"""Speaker cutout with Robust Video Matting (CPU). python3 matte.py src.mp4 alpha.mp4 rvm.torchscript
Writes a grayscale H.264 matte at 720x1280, framed exactly like the Reel (fill + centre crop)."""
import sys, subprocess, numpy as np, torch, time
torch.set_num_threads(8)
SRC, OUT, MODEL = sys.argv[1:4]; W, H = 720, 1280
m = torch.jit.load(MODEL).eval()
vf = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', SRC, '-map', '0:v:0', '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                        '-c:v', 'libx264', '-crf', '8', '-preset', 'fast', '-pix_fmt', 'yuv420p', OUT], stdin=subprocess.PIPE)
rec = [None] * 4; n = 0; t0 = time.time()
with torch.no_grad():
    while True:
        b = dec.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        x = torch.from_numpy(np.frombuffer(b, np.uint8).reshape(H, W, 3).copy()).permute(2, 0, 1)[None].float() / 255
        _, pha, *rec = m(x, *rec, 0.4)
        enc.stdin.write((pha[0, 0].clamp(0, 1) * 255).byte().numpy().tobytes()); n += 1
        if n % 150 == 0: print(f'matte {n} frames {n / (time.time() - t0):.1f} fps', flush=True)
enc.stdin.close(); enc.wait(); print('MATTE OK', n)
