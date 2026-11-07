# KazuPlayer：スマホで動かすための ONNX 書き出し・int8 で小さくする・速さを測る（kp_onnx_kaggle_v3、2026-11-07：長さが変わっても動く ONNX にし、小さくする方法を4通り比べ、腿と3行を歌わせる。Kaggle がデータセットの中の zip を展開してフォルダにしても動くように。Kaggle 版。画面を閉じても最後まで動く。重みはドライブの共有リンク WLINK から）
import subprocess, sys, os, time
def sh(c):
    print('$', c[:120]); r = subprocess.run(c, shell=True, text=True, capture_output=True)
    if r.returncode != 0: print(r.stdout[-2000:], r.stderr[-3000:]); raise SystemExit('止まりました：上の行を写真で送ってください')
    return r.stdout
import torch
assert torch.cuda.is_available(), 'GPU がありません。「ランタイム」→「ランタイムのタイプを変更」→ T4 GPU を選んでから、もう一度'
print('GPU:', torch.cuda.get_device_name(0), ' PyTorch', torch.__version__)
sh('apt-get -qq install -y espeak-ng > /dev/null')
sh('pip -q install hydra-core omegaconf einops einops-exts ema-pytorch alias-free-torch "x-transformers==2.1.2" "vector-quantize-pytorch==1.23.2" '
   'torchdiffeq safetensors jieba pypinyin cn2an inflect "phonemizer==3.3.0" "py3langid==0.3.0" onnxruntime soundfile librosa huggingface_hub')
if not os.path.exists('/tmp/kp/ys/src/YingMusicSinger/infer/YingMusicSinger.py'):
    sh('git clone -q --depth 1 https://github.com/ASLP-lab/YingMusic-Singer-Plus.git /tmp/kp/ys')
# dac の部品（使う3つだけ。本物は依存が多い）
os.makedirs('/tmp/kp/shim/dac/nn', exist_ok=True)
open('/tmp/kp/shim/dac/__init__.py', 'w').close(); open('/tmp/kp/shim/dac/nn/__init__.py', 'w').close()
open('/tmp/kp/shim/dac/nn/layers.py', 'w').write('''import torch, torch.nn as nn
from torch.nn.utils import weight_norm
def WNConv1d(*a, **k): return weight_norm(nn.Conv1d(*a, **k))
def WNConvTranspose1d(*a, **k): return weight_norm(nn.ConvTranspose1d(*a, **k))
def snake(x, alpha):
    s = x.shape; x = x.reshape(s[0], s[1], -1)
    x = x + (alpha + 1e-9).reciprocal() * torch.sin(alpha * x).pow(2)
    return x.reshape(s)
class Snake1d(nn.Module):
    def __init__(self, channels):
        super().__init__(); self.alpha = nn.Parameter(torch.ones(1, channels, 1))
    def forward(self, x): return snake(x, self.alpha)
''')
open('/tmp/kp/shim/dac/nn/quantize.py', 'w').write('import torch.nn as nn\nclass ResidualVectorQuantize(nn.Module):\n    def __init__(self, *a, **k): raise RuntimeError("unused")\n')
# 注意の計算の CUDA 専用の書き方を外す（新しい PyTorch で無いことがある）
p = '/tmp/kp/ys/src/YingMusicSinger/melody/Gconform.py'; s = open(p).read()
if 'sdp_kernel(enable_math=False)' in s:
    s = 'import contextlib\n' + s.replace('with torch.backends.cuda.sdp_kernel(enable_math=False):', 'with contextlib.nullcontext():'); open(p, 'w').write(s)
import contextlib, torch.backends.cuda as _c
if not hasattr(_c, 'sdp_kernel'): _c.sdp_kernel = lambda *a, **k: contextlib.nullcontext()
# 音の読み書きは soundfile で（torchaudio の新しい版は別の部品を要求する）
import torchaudio, soundfile as sf, numpy as np
def _load(path, *a, **k):
    d, sr = sf.read(str(path), dtype='float32', always_2d=True); return torch.from_numpy(d.T.copy()), sr
def _save(path, src, sample_rate, *a, **k):
    x = src.detach().cpu().float().numpy(); x = x if x.ndim == 2 else x[None]; sf.write(str(path), x.T, int(sample_rate))
torchaudio.load = _load; torchaudio.save = _save
os.chdir('/tmp/kp/ys'); sys.path[:0] = ['/tmp/kp/shim', '/tmp/kp/ys']
from huggingface_hub import hf_hub_download
R = 'ASLP-lab/YingMusic-Singer-Plus'
CFG = hf_hub_download(R, 'config.json'); WP = hf_hub_download(R, 'model.safetensors')
print('準備OK（AIの重み）', os.path.getsize(WP) // 2**20, 'MB')

# %% [markdown]
# ## 2. かな → 発音記号、AIの組み立て（すぐ終わる）

# %%
import json, gc, random
import torch.nn as nn, hydra
from omegaconf import OmegaConf
from safetensors import safe_open
from src.YingMusicSinger.infer.YingMusicSinger import YingMusicSinger
cfg = json.load(open(CFG))
TBL = {}
for c, ks in {'k':'かきくけこ','s':'さしすせそ','t':'たちつてと','n':'なにぬねの','h':'はひふへほ','m':'まみむめも','j':'や_ゆ_よ','ɾ':'らりるれろ','w':'わ___を',
              'g':'がぎぐげご','z':'ざじずぜぞ','d':'だぢづでど','b':'ばびぶべぼ','p':'ぱぴぷぺぽ'}.items():
    for k, v in zip(ks, ['a','i','ɯ','e','o']):
        if k != '_': TBL[k] = [c, v]
for k, v in {'あ':'a','い':'i','う':'ɯ','え':'e','お':'o'}.items(): TBL[k] = [v]
TBL.update({'し':['ɕ','i'],'ち':['tɕ','i'],'つ':['ts','ɯ'],'ひ':['ç','i'],'ふ':['ɸ','ɯ'],'じ':['dʑ','i'],'ぢ':['dʑ','i'],'づ':['z','ɯ'],'を':['o'],'ん':['ɴ'],'っ':['q'],'ー':['ː'],'ゔ':['b','ɯ']})
YO = {'ゃ':'a','ゅ':'ɯ','ょ':'o'}; SM = {'ぁ':'a','ぃ':'i','ぅ':'ɯ','ぇ':'e','ぉ':'o'}
PAL = {'き':'kj','ぎ':'gj','に':'nj','ひ':'ç','み':'mj','り':'ɾj','び':'bj','ぴ':'pj','し':'ɕ','ち':'tɕ','じ':'dʑ'}
SMB = {'う':'w','て':'t','で':'d','と':'t','ど':'d','ふ':'ɸ','ち':'tɕ','じ':'dʑ','し':'ɕ','ゔ':'b'}
def kana2ph(s):
    out = []; i = 0
    while i < len(s):
        c = s[i]; n = s[i+1] if i + 1 < len(s) else ''
        if n in YO and c in PAL: out += [PAL[c], YO[n]]; i += 2; continue
        if n in SM and c in SMB: out += [SMB[c], SM[n]]; i += 2; continue
        if c == 'ー':
            if out and out[-1] in ('a','i','ɯ','e','o'): out.append(out[-1])   # 伸ばす音＝前の母音をもう一度（きりたんの書き方）
            i += 1; continue
        if c in TBL: out += TBL[c]
        elif c in ' 　、,，':
            if out and out[-1] != ',': out.append(',')   # 歌詞の区切り＝息つぎ（YingMusic は句読点を「,」にして渡す）
        else: raise KeyError(c)
        i += 1
    return out

def build(parts):
    s = YingMusicSinger.__new__(YingMusicSinger); nn.Module.__init__(s)
    s.cfg = OmegaConf.load(cfg['model_cfg_path']); s.melody_input_source = s.cfg.model.melody_input_source
    s.is_tts_pretrain = s.cfg.model.is_tts_pretrain
    s._need_midi = s.melody_input_source in {'some_pretrain', 'some_pretrain_fuzzdisturb', 'some_pretrain_postprocess_embedding'}
    s.vae_frame_rate = 44100 / 2048; s.rear_silent_time = 1.0
    if 'model' in parts:
        from src.YingMusicSinger.models.model import Singer
        mc = hydra.utils.get_class(f'src.YingMusicSinger.models.{s.cfg.model.backbone}')
        s.model = Singer(transformer=mc(**s.cfg.model.arch, text_num_embeds=s.cfg.datasets_cfg.text_num_embeds, mel_dim=s.cfg.model.mel_spec.n_mel_channels, use_guidance_scale_embed=False),
                         mel_spec_kwargs=s.cfg.model.mel_spec, is_tts_pretrain=s.is_tts_pretrain, melody_input_source=s.melody_input_source,
                         cka_disabled=s.cfg.model.cka_disabled, num_channels=None, extra_parameters=s.cfg.extra_parameters, distill_stage=1, use_guidance_scale_embed=False)
    if 'vae' in parts:
        from src.YingMusicSinger.utils.stable_audio_tools.vae_copysyn import StableAudioInfer
        s.vae = StableAudioInfer(model_config_path=cfg['vae_config_path'], model_ckpt_path=None)
    if 'midi' in parts:
        from src.YingMusicSinger.melody.midi_extractor import MIDIExtractor
        from src.YingMusicSinger.utils.mel_spectrogram import MelodySpectrogram
        from src.YingMusicSinger.utils.cnen_tokenizer import CNENTokenizer
        s.midi_teacher = MIDIExtractor(); s.melody_spectrogram_extract = MelodySpectrogram(); s.cnen_tokenizer = CNENTokenizer()
        P = s.cnen_tokenizer.phone2id
        s.cnen_tokenizer.encode = lambda text: [P[p] for p in (text.strip()[1:].split() if text.strip().startswith('§') else kana2ph(text))]   # 歌詞はかなで渡す（§ で始まるときは発音記号を空白区切りで）
    sd = s.state_dict(); left = set(sd)
    with safe_open(WP, framework='pt', device='cpu') as f:
        for k in f.keys():
            if k in sd and tuple(f.get_slice(k).get_shape()) == tuple(sd[k].shape): sd[k].copy_(f.get_tensor(k)); left.discard(k)
    print('作った部分', parts, '入らなかった重み', len(left))
    assert len(left) < 20
    return s
print('かなの例', kana2ph('べんちのよこでももをあげる'), kana2ph('きーぱーのじゅうしん,あいたいっぽ'))

import glob, zipfile, shutil
os.makedirs('/tmp/kp', exist_ok=True)
# 入力：Kaggle は上げた zip を自動で展開する（中の zip までフォルダになる）ので、zip でもフォルダでも動くようにする
def find_pack(name):
    z = glob.glob(f'/kaggle/input/**/{name}.zip', recursive=True)
    out = f'/tmp/kp/{name}'
    if z: zipfile.ZipFile(z[0]).extractall(out); return out
    d = [p for p in glob.glob(f'/kaggle/input/**/{name}', recursive=True) if os.path.isdir(p)]
    assert d, f'データセットに {name} がありません（「Add Input」でデータセットを追加）'
    c = glob.glob(f'{d[0]}/**/cases.json', recursive=True); assert c, f'{name} に cases.json がありません'
    shutil.copytree(os.path.dirname(c[0]), out, dirs_exist_ok=True); return out
PK2, PK5 = find_pack('kp_test_pack_v2'), find_pack('kp_test_pack_v5')
YC = glob.glob('/kaggle/input/**/kp_yms_clip.wav', recursive=True); assert YC, 'データセットに kp_yms_clip.wav がありません'
D = '/tmp/kp'
OUTD = '/kaggle/working'; os.makedirs(OUTD, exist_ok=True)
import torch.nn as nn
WFT = glob.glob('/kaggle/input/**/singer_ja_pjs_v4.pt', recursive=True)
if not WFT:
    assert 'WLINK' in globals() and WLINK.startswith('http'), '最初のセルの WLINK に、ドライブの singer_ja_pjs_v4.pt の共有リンクを入れてください'
    sh('pip -q install gdown'); import gdown
    gdown.download(WLINK, '/tmp/kp/singer_ja_pjs_v4.pt', fuzzy=True, quiet=False); WFT = ['/tmp/kp/singer_ja_pjs_v4.pt']
    assert os.path.getsize(WFT[0]) > 5e8, '重みを取れませんでした（共有が「リンクを知っている全員」になっているか確認）'
s = build(['vae', 'midi']).cuda().eval()
# 確かめ用の歌（前に使った14行・腿・12の句）を先に用意
T = '/tmp/kp/kt'; os.makedirs(T, exist_ok=True)
for P in (PK2, PK5): shutil.copytree(P, T, dirs_exist_ok=True)
cases = json.load(open(f'{PK2}/cases.json')) + json.load(open(f'{PK5}/cases.json'))
TEST = YC[0]
print('確かめ用の歌', len(cases), '行', flush=True)
preps = {}
def prep(name, wav, ref, tgt):
    with torch.no_grad():
        r = s.prepare_input(ref_audio_path=wav, melody_audio_path=wav, ref_text=ref.replace(' ', ','), target_text=tgt.replace(' ', ','), sil_len_to_end=0.5, lrc_align_mode='sentence_level')
    preps[name] = [x.cpu() if torch.is_tensor(x) else x for x in r]
prep('momo', TEST, 'べんちのよこでたいをあげる', 'べんちのよこでももをあげる')
for c in cases: prep(c['name'], f"{T}/{c['name']}.wav", c['ref'], c['tgt'])
VAE_SD = {k: v.cpu() for k, v in s.vae.state_dict().items()}
del s; gc.collect(); torch.cuda.empty_cache()

m = build(['model']); singer = m.model
base = {k: v.detach().clone() for k, v in singer.state_dict().items()}
ft = torch.load(WFT[0], map_location='cpu')
A = 0.5
singer.load_state_dict({k: (base[k].float() + A * (ft[k].float() - base[k].float())) if k in ft and base[k].is_floating_point() else base[k] for k in base})
del base, ft; gc.collect()
singer = singer.cuda().eval()
# 1) 行ごとに本物の入力をつかまえる（1段だけ動かして入力を記録）
NAMES = ['momo', '17a', '02a', '13d']
caps = {}
orig = singer.transformer.forward
for nm in NAMES:
    cap = {}
    def hook(*a, **k):
        if 'x' not in cap: cap.update({kk: (v.detach().cpu() if torch.is_tensor(v) else v) for kk, v in k.items()})
        return orig(*a, **k)
    singer.transformer.forward = hook
    ref_latent, ref_len, text, total, midi_in, midi_p, bound_p = [x.cuda() if torch.is_tensor(x) else x for x in preps[nm]]
    with torch.inference_mode():
        singer.sample(cond=ref_latent, midi_in=midi_in, text=text, duration=total, steps=1, cfg_strength=3.0, sway_sampling_coef=None,
                      use_epss=False, seed=7, midi_p=midi_p, t_shift=0.5, bound_p=bound_p, guidance_scale=3.0)
    caps[nm] = (cap, ref_len)
    print('入力', nm, tuple(cap['x'].shape), flush=True)
singer.transformer.forward = orig
class Step(nn.Module):
    def __init__(s, tr): super().__init__(); s.tr = tr
    def forward(s, x, cond, text, midi, t):
        p, _ = s.tr(x=x, cond=cond, text=text, midi=midi, time=t, mask=None, cfg_infer=True, cache=False, cfg_infer_ids=(True, False, False, True))
        a, b = torch.chunk(p, 2, dim=0); return a + (a - b) * 3.0
step = Step(singer.transformer.float().cpu()).eval()
def feed_of(cap, x=None, t=None):
    return {'x': (cap['x'] if x is None else x).numpy().astype(np.float32), 'cond': cap['cond'].numpy(), 'text': cap['text'].numpy(), 'midi': cap['midi'].numpy(),
            't': (cap['time'] if t is None else t).numpy().astype(np.float32)}
# 2) 長さが変わっても動く形で ONNX に
OD = '/tmp/kp/onnx'; os.makedirs(OD, exist_ok=True); F32 = f'{OD}/dit_a05_f32.onnx'
c0 = caps['momo'][0]
with torch.no_grad():
    torch.onnx.export(step, (c0['x'], c0['cond'], c0['text'], c0['midi'], c0['time']), F32, input_names=['x', 'cond', 'text', 'midi', 't'], output_names=['v'],
                      opset_version=18, dynamo=False, dynamic_axes={'x': {1: 'n'}, 'cond': {1: 'n'}, 'text': {1: 'nt'}, 'midi': {1: 'n'}, 'v': {1: 'n'}})
print('ONNX 書き出し', os.path.getsize(F32) // 2**20, 'MB', flush=True)
import onnxruntime as ort, onnx
from onnxruntime.quantization import quantize_dynamic, QuantType
from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer
VAR = {'f32': F32}
try:
    p = f'{OD}/dit_a05_q8b32.onnx'; q = MatMulNBitsQuantizer(F32, bits=8, block_size=32, is_symmetric=True, accuracy_level=4); q.process(); q.model.save_model_to_file(p, True); VAR['q8b32'] = p
except Exception as e: print('8bit（ブロック）できず', repr(e)[:300])
try:
    p = f'{OD}/dit_a05_q4b32.onnx'; q = MatMulNBitsQuantizer(F32, bits=4, block_size=32, is_symmetric=True, accuracy_level=4); q.process(); q.model.save_model_to_file(p, True); VAR['q4b32'] = p
except Exception as e: print('4bit（ブロック）できず', repr(e)[:300])
try:
    p = f'{OD}/dit_a05_i8pc.onnx'; quantize_dynamic(F32, p, weight_type=QuantType.QInt8, per_channel=True); VAR['i8pc'] = p
except Exception as e: print('int8（列ごと）できず', repr(e)[:300])
def size_mb(p): return sum(os.path.getsize(os.path.join(os.path.dirname(p), f)) for f in os.listdir(os.path.dirname(p)) if f.startswith(os.path.basename(p))) // 2**20
# 3) 各行で：torch とのずれ（1段）・1段の秒数
res = {}; SES = {}
for vn, vp in VAR.items():
    so = ort.SessionOptions(); so.intra_op_num_threads = 4
    se = ort.InferenceSession(vp, so, providers=['CPUExecutionProvider']); SES[vn] = se
    r = {'MB': size_mb(vp)}
    for nm in NAMES:
        cap = caps[nm][0]; f = feed_of(cap)
        with torch.no_grad(): ref = step(cap['x'], cap['cond'], cap['text'], cap['midi'], cap['time']).numpy()
        v = se.run(None, f)[0]; t1 = time.time(); se.run(None, f); dt = time.time() - t1
        r[nm] = (round(float(np.abs(v - ref).max() / (np.abs(ref).max() + 1e-9)), 4), round(dt, 3), int(cap['x'].shape[1]))
    res[vn] = r; print(vn, r, flush=True)
# 4) 各方式で32段まるごと歌わせる（f32 は16段も）
lats = {}
def run(se, cap, ref_len, steps):
    dur = cap['x'].shape[1]; torch.manual_seed(7); y = torch.randn(dur, cap['x'].shape[2], device='cuda').cpu().unsqueeze(0).numpy()
    ts = torch.linspace(0, 1, steps + 1); ts = (0.5 * ts / (1 + (0.5 - 1) * ts)).numpy()
    for k in range(steps):
        v = se.run(None, feed_of(cap, x=torch.from_numpy(y), t=torch.tensor([ts[k]], dtype=torch.float32).reshape(cap['time'].shape)))[0]
        y = y + (ts[k+1] - ts[k]) * v
    return torch.from_numpy(y).float()[:, ref_len:-int(44100/2048*1.0), :].permute(0, 2, 1)
for vn, se in SES.items():
    for nm in NAMES:
        cap, ref_len = caps[nm]; t1 = time.time()
        lats[f'{nm}_{vn}_32'] = run(se, cap, ref_len, 32)
        if vn == 'f32': lats[f'{nm}_{vn}_16'] = run(se, cap, ref_len, 16)
        print('歌わせた', nm, vn, f'{time.time()-t1:.0f}秒', flush=True)
del singer, m; gc.collect(); torch.cuda.empty_cache()
v = build(['vae']).cuda().eval(); v.vae.load_state_dict(VAE_SD)
from src.YingMusicSinger.utils.smooth_ending import smooth_ending
from einops import rearrange
OUT = '/tmp/kp/onnx_out'; os.makedirs(OUT, exist_ok=True)
for nm, lat in lats.items():
    with torch.no_grad(): a = v.vae.decode_audio(lat.cuda())
    a = smooth_ending(rearrange(a, 'b d n -> d (b n)').float().cpu(), 44100)
    sf.write(f'{OUT}/{nm}.wav', a.numpy().T, 44100)
json.dump(res, open(f'{OUT}/onnx_check.json', 'w'), ensure_ascii=False)
for nm in NAMES: np.savez(f'{OUT}/in_{nm}.npz', **feed_of(caps[nm][0]))
zp = shutil.make_archive(f'{OUTD}/kp_onnx_out_v3', 'zip', OUT)
for vn in ('q8b32', 'q4b32'):
    if vn in VAR:
        for f in os.listdir(OD):
            if f.startswith(os.path.basename(VAR[vn])): shutil.copy(f'{OD}/{f}', OUTD)
print('完了：右の「Output」にある kp_onnx_out_v3.zip を送ってください')
