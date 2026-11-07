# KazuPlayer の Kaggle 用の起動役（run.py）。Kaggle のセルは固定で、これを GitHub から取ってきて動かす。
# 最初の1分で全部を点検し、足りないものは自分で入れ、無理なものは日本語で理由を出して止まる。
# 動かす仕事は tools/kaggle/JOB.txt に書いた名前（jobs/<名前>.py）。
import os, sys, glob, json, time, subprocess, urllib.request
REPO = 'kazuSato-Japan/KazuPlayer'
def log(*a): print(time.strftime('[%H:%M:%S]'), *a, flush=True)
def stop(msg):
    log('■ 止まりました：' + msg); log('■ この画面の写真を送ってください'); raise SystemExit(1)
def gh(path):
    q = urllib.request.Request(f'https://api.github.com/repos/{REPO}/contents/{path}?ref=main',
                               headers={'Accept': 'application/vnd.github.raw', 'User-Agent': 'kazuplayer-kaggle'})
    return urllib.request.urlopen(q, timeout=30).read().decode()
log('==== 点検を始めます ====')
# 1) ネット
try: JOB = gh('tools/kaggle/JOB.txt').strip()
except Exception as e: stop(f'インターネットにつながりません（右の「Settings」→「Internet」を On に）：{e}')
log('ネット OK、動かす仕事：', JOB)
# 2) GPU
r = subprocess.run('nvidia-smi --query-gpu=name --format=csv,noheader', shell=True, text=True, capture_output=True)
if r.returncode != 0 or not r.stdout.strip(): stop('GPU がありません（右の「Settings」→「Accelerator」を GPU T4 x2 に）')
log('GPU OK：', r.stdout.strip().splitlines()[0])
# 3) 入力（データセット）
packs = glob.glob('/kaggle/input/**/kp_test_pack_v*', recursive=True)
if not packs: stop('入力のデータセットが付いていません（右の「Input」に kp-kaggle-in が出ているか確認。無ければ「Add Input」で付ける）')
log('入力 OK：', len(packs), '個')
# 4) 重みのリンク
if not globals().get('WLINK'): stop('セルの1行目 WLINK が消えています')
# 5) 部品（足りなければ入れる）
for mod, pkg in [('onnx', 'onnx'), ('onnx_ir', 'onnx-ir'), ('onnxruntime', 'onnxruntime'), ('gdown', 'gdown'), ('soundfile', 'soundfile')]:
    try: __import__(mod)
    except ImportError:
        log('入れています：', pkg)
        r = subprocess.run(f'pip -q install {pkg}', shell=True, text=True, capture_output=True)
        if r.returncode != 0: stop(f'{pkg} が入りません：{r.stderr[-500:]}')
log('部品 OK')
log('==== 点検おわり。仕事を始めます ====')
src = gh(f'tools/kaggle/jobs/{JOB}.py')
exec(compile(src, f'jobs/{JOB}.py', 'exec'), globals())
log('==== 全部おわり ====')
