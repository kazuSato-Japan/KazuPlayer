# KazuPlayer：スマホで歌い直しを最初から最後まで動かすための部品づくり（export_parts_v1、2026-11-07）。声→数字・数字→声・メロディ読みを ONNX に、α0.5/0.7 で乱数6通り、ONNX だけで通し。Kaggle で GitHub の run.py から動く
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

# ====== ここから export_parts_v1 の本体 ======
# 1) スマホで残っている部品3つ（声→数字・数字→声・メロディ読み）を ONNX にし、torch と同じになるか確かめる
# 2) α0.5 と α0.7 の両方で、乱数6通りずつ歌わせる（スマホに入れるAIを1つに絞るため）
# 3) ONNX だけで最初から最後まで歌わせる（スマホと同じ道）
# どこかで失敗しても、ほかの部分は続けて、最後に結果をまとめて出す
import traceback
REPORT = {}
def part(name):
    def deco(fn):
        t0 = time.time()
        try:
            fn(); REPORT[name] = {'ok': True, 'sec': round(time.time() - t0)}
            print(f'■ {name}：できました（{time.time()-t0:.0f}秒）', flush=True)
        except Exception as e:
            REPORT[name] = {'ok': False, 'err': repr(e)[:800]}
            print(f'■ {name}：失敗', flush=True); traceback.print_exc()
        return fn
    return deco
OUT = '/tmp/kp/parts_out'; os.makedirs(OUT, exist_ok=True); os.makedirs(f'{OUT}/gen', exist_ok=True); os.makedirs(f'{OUT}/e2e', exist_ok=True); os.makedirs(f'{OUT}/phone', exist_ok=True)
OD = '/tmp/kp/onnx'; os.makedirs(OD, exist_ok=True)
import onnxruntime as ort, onnx
import torch.nn.functional as F
def sess(p, th=4):
    so = ort.SessionOptions(); so.intra_op_num_threads = th
    return ort.InferenceSession(p, so, providers=['CPUExecutionProvider'])
def rel(a, b):
    a = np.asarray(a, np.float64); b = np.asarray(b, np.float64)
    return round(float(np.abs(a - b).max() / (np.abs(b).max() + 1e-9)), 5)
def mono44(path):
    d, sr0 = sf.read(path, dtype='float32', always_2d=True)
    assert sr0 == 44100, f'{path} が 44100Hz ではありません（{sr0}）'
    return d.mean(1)

# ---- 準備：歌う行（14行＋12の句＋腿）と torch の基準 ----
s = build(['vae', 'midi']).cuda().eval()
T = '/tmp/kp/kt'; os.makedirs(T, exist_ok=True)
for P in (PK2, PK5): shutil.copytree(P, T, dirs_exist_ok=True)
cases = json.load(open(f'{PK2}/cases.json')) + json.load(open(f'{PK5}/cases.json'))
WAV = {'momo': YC[0]}; TXT = {'momo': ('べんちのよこでたいをあげる', 'べんちのよこでももをあげる')}
for c in cases: WAV[c['name']] = f"{T}/{c['name']}.wav"; TXT[c['name']] = (c['ref'], c['tgt'])
ALL = list(WAV)
print('歌う行', len(ALL), ALL, flush=True)
preps = {}
for nm in ALL:
    ref, tgt = TXT[nm]
    with torch.no_grad():
        r = s.prepare_input(ref_audio_path=WAV[nm], melody_audio_path=WAV[nm], ref_text=ref.replace(' ', ','), target_text=tgt.replace(' ', ','), sil_len_to_end=0.5, lrc_align_mode='sentence_level')
    preps[nm] = [x.cpu() if torch.is_tensor(x) else x for x in r]
NAMES = ['momo', '17a', '02a', '13d']
VAE_SD = {k: v.cpu() for k, v in s.vae.state_dict().items()}
vae_cpu = s.vae.model.float().cpu().eval()
mte_cpu = s.midi_teacher.float().cpu().eval(); msx = s.melody_spectrogram_extract.cpu()
json.dump(s.cnen_tokenizer.phone2id, open(f'{OUT}/phone2id.json', 'w'), ensure_ascii=False)
# スマホ確かめ用の材料（歌・歌詞の記号列・長さ）
for nm in ALL:
    ref_latent, ref_len, text, total = preps[nm][:4]
    np.savez(f'{OUT}/phone/case_{nm}.npz', wav=mono44(WAV[nm]).astype(np.float32), tokens=text.numpy().astype(np.int64), ref_len=np.int64(ref_len), total_len=np.int64(total),
             ref_text=np.array(TXT[nm][0]), tgt_text=np.array(TXT[nm][1]))

# ---- 部品1：声→数字（VAE エンコーダ）。音量を −6dB にそろえるところまで中に入れる ----
class Enc(nn.Module):
    def __init__(s_, m): super().__init__(); s_.m = m
    def forward(s_, audio):          # audio [1, 2, N]（44100Hz、モノラルなら同じものを2つ）
        a = audio * (10.0 ** (-6 / 20.0)) / audio.abs().max()
        h = s_.m.encoder(a)
        mean, scale = h.chunk(2, dim=1)
        return mean, F.softplus(scale) + 1e-4   # 数字 = mean + std × 乱数（乱数はアプリ側で）
class Dec(nn.Module):
    def __init__(s_, m): super().__init__(); s_.m = m
    def forward(s_, lat): return s_.m.decode(lat)   # lat [1, 64, T] → [1, 2, T×2048]
ENC, DEC, MEL = f'{OD}/vae_enc.onnx', f'{OD}/vae_dec.onnx', f'{OD}/melody.onnx'
def pad_sil(w, sec): return np.concatenate([w, np.zeros(int(44100 * sec), np.float32)])
def st(w): return torch.from_numpy(np.stack([w, w])[None].astype(np.float32))
TIMES = {}
@part('声→数字の部品')
def _enc():
    assert vae_cpu.pretransform is None
    enc = Enc(vae_cpu).eval(); x0 = st(pad_sil(mono44(WAV['momo']), 0.5))
    with torch.no_grad():
        torch.onnx.export(enc, (x0,), ENC, input_names=['audio'], output_names=['mean', 'std'], opset_version=18, dynamo=False,
                          dynamic_axes={'audio': {2: 'n'}, 'mean': {2: 't'}, 'std': {2: 't'}})
    se = sess(ENC); r = {'MB': os.path.getsize(ENC) // 2**20}
    for nm in NAMES:
        x = st(pad_sil(mono44(WAV[nm]), 0.5))
        with torch.no_grad(): m_ref, s_ref = enc(x)
        t1 = time.time(); m, sd = se.run(None, {'audio': x.numpy()}); dt = time.time() - t1
        # torch の本物の通り道（prepare_audio→normalize→encode）と長さが同じかも見る
        r[nm] = {'mean_ずれ': rel(m, m_ref.numpy()), 'std_ずれ': rel(sd, s_ref.numpy()), '長さ': int(m.shape[2]), '本物の長さ': int(preps[nm][1]), '秒': round(dt, 2)}
        assert m.shape[2] == preps[nm][1], f'{nm} の長さが違う'
    REPORT['enc_detail'] = r; print(r, flush=True)
@part('数字→声の部品')
def _dec():
    dec = Dec(vae_cpu).eval(); l0 = preps['momo'][0].transpose(1, 2).float()[:, :, :60]
    with torch.no_grad():
        torch.onnx.export(dec, (l0,), DEC, input_names=['latent'], output_names=['audio'], opset_version=18, dynamo=False,
                          dynamic_axes={'latent': {2: 't'}, 'audio': {2: 'n'}})
    se = sess(DEC); r = {'MB': os.path.getsize(DEC) // 2**20}
    for nm in NAMES:
        l = preps[nm][0].transpose(1, 2).float()
        with torch.no_grad(): a_ref = dec(l).numpy()
        t1 = time.time(); a = se.run(None, {'latent': l.numpy()})[0]; dt = time.time() - t1
        r[nm] = {'ずれ': rel(a, a_ref), '長さ': int(l.shape[2]), '秒': round(dt, 2)}
    REPORT['dec_detail'] = r; print(r, flush=True)

# ---- 部品3：メロディ読み（メル→MIDI 抽出→長さ合わせ→間引き→最初の見本部分を消す）----
class Melody(nn.Module):
    def __init__(s_, ms, mte):
        super().__init__(); s_.mte = mte
        n = torch.arange(2048, dtype=torch.float64); k = torch.arange(1025, dtype=torch.float64)[:, None]
        win = torch.hann_window(2048, dtype=torch.float64)
        ang = 2 * np.pi * k * n / 2048
        W = torch.cat([torch.cos(ang) * win, -torch.sin(ang) * win], 0).float()[:, None, :]   # [2050, 1, 2048]
        s_.register_buffer('W', W); s_.register_buffer('mb', ms.mel_basis.float().clone())
    def mel(s_, a):                       # a [1, N] → [1, 80, T]（torch.stft center=True・reflect と同じ）
        x = F.pad(a[:, None, :], (1024, 1024), mode='reflect')
        y = F.conv1d(x, s_.W, stride=512)
        re, im = y[:, :1025], y[:, 1025:]
        mag = torch.sqrt(re * re + im * im)
        return torch.log(torch.clamp(torch.matmul(s_.mb, mag), min=1e-5))
    def forward(s_, ref_audio, mel_audio, grid, ref_len):
        m = torch.cat([s_.mel(ref_audio), s_.mel(mel_audio)], dim=2).transpose(1, 2)
        midi_p, _ = s_.mte(m)                               # [1, Tin, 128]
        tin = torch.ones_like(midi_p[:, :, 0]).sum(1)        # Tin（数として）
        L = torch.ones_like(grid).sum(1)
        idx = torch.cumsum(torch.ones_like(grid), 1) - 1     # 0..L-1
        src = torch.clamp((idx + 0.5) * tin / L - 0.5, min=0.0)
        i0 = torch.floor(src); lam = (src - i0)[0][:, None]
        i0l = i0.long()[0]; i1l = torch.minimum(i0l + 1, (tin - 1).long())
        a = torch.index_select(midi_p[0], 0, i0l); b = torch.index_select(midi_p[0], 0, i1l)
        x = torch.sigmoid((1 - lam) * a + lam * b)[None]     # [1, L, 128]
        keep = ((idx - torch.floor(idx / 10) * 10) != 0).float()          # 10こまに1こ消す（drop [1,9]）
        keep = keep * (idx >= ref_len.float()).float()                     # 見本の部分は消す
        return x * keep[:, :, None]
@part('メロディ読みの部品')
def _mel():
    mm = Melody(msx, mte_cpu).eval()
    from src.YingMusicSinger.models.model import interpolation_midi_continuous
    from src.YingMusicSinger.melody.SmoothMelody import MIDIFuzzDisturb
    fz = MIDIFuzzDisturb(dim=128, drop_prob=[1, 9], noise_scale=0.0, blur_kernel=0, drop_type='equal_space')
    def args(nm):
        w = mono44(WAV[nm]); total = int(preps[nm][3])
        return (torch.from_numpy(pad_sil(w, 0.5))[None], torch.from_numpy(pad_sil(w, 1.0))[None], torch.zeros(1, total), torch.tensor([int(preps[nm][1])], dtype=torch.int64))
    def ref_midi(nm):   # 元の作りと同じ手順（torch）
        w = mono44(WAV[nm]); ra = torch.from_numpy(pad_sil(w, 0.5))[None]; ma = torch.from_numpy(pad_sil(w, 1.0))[None]
        with torch.no_grad():
            mel = torch.cat([msx(audio=ra, sr=44100), msx(audio=ma, sr=44100)], dim=2)
            midi_p, bound_p = mte_cpu(mel.transpose(1, 2))
            total = int(preps[nm][3]); midi, _ = interpolation_midi_continuous(midi_p=midi_p, bound_p=bound_p, total_len=total)
            midi = fz(midi); midi[:, :int(preps[nm][1])] = 0
        return midi.numpy(), mel.numpy()
    a0 = args('momo')
    with torch.no_grad():
        torch.onnx.export(mm, a0, MEL, input_names=['ref_audio', 'mel_audio', 'grid', 'ref_len'], output_names=['midi'], opset_version=18, dynamo=False,
                          dynamic_axes={'ref_audio': {1: 'n1'}, 'mel_audio': {1: 'n2'}, 'grid': {1: 'L'}, 'midi': {1: 'L'}})
    se = sess(MEL); r = {'MB': os.path.getsize(MEL) // 2**20}
    for nm in NAMES:
        ra, ma, g, rl = args(nm); want, wmel = ref_midi(nm)
        with torch.no_grad(): mine_t = mm(ra, ma, g, rl).numpy(); mymel = torch.cat([mm.mel(ra), mm.mel(ma)], 2).numpy()
        t1 = time.time(); got = se.run(None, {'ref_audio': ra.numpy(), 'mel_audio': ma.numpy(), 'grid': g.numpy(), 'ref_len': rl.numpy()})[0]; dt = time.time() - t1
        r[nm] = {'メルのずれ(絶対)': round(float(np.abs(mymel - wmel).max()), 4), 'torch版と元のずれ': rel(mine_t, want), 'ONNXと元のずれ': rel(got, want), '秒': round(dt, 2)}
    REPORT['mel_detail'] = r; print(r, flush=True)

# ---- AI本体：α0.5・α0.7 で乱数6通り（torch・GPU）＋ q4b32 の ONNX ----
from src.YingMusicSinger.utils.smooth_ending import smooth_ending
from einops import rearrange
del s; gc.collect(); torch.cuda.empty_cache()
vg = build(['vae']).cuda().eval(); vg.vae.load_state_dict(VAE_SD)
def dec_save(lat, path):
    with torch.no_grad(): a = vg.vae.decode_audio(lat.cuda())
    a = smooth_ending(rearrange(a, 'b d n -> d (b n)').float().cpu(), 44100); sf.write(path, a.numpy().T, 44100)
m = build(['model']); singer = m.model
base = {k: v.detach().clone() for k, v in singer.state_dict().items()}
ft = torch.load(WFT[0], map_location='cpu')
SEEDS = [7, 666, 1, 2, 3, 4]
class Step(nn.Module):
    def __init__(s_, tr): super().__init__(); s_.tr = tr
    def forward(s_, x, cond, text, midi, t):
        p, _ = s_.tr(x=x, cond=cond, text=text, midi=midi, time=t, mask=None, cfg_infer=True, cache=False, cfg_infer_ids=(True, False, False, True))
        a, b = torch.chunk(p, 2, dim=0); return a + (a - b) * 3.0
CAPS = {}
DITQ = {}
for A in (0.5, 0.7):
    tag = f'a{int(A*10)}'
    singer.load_state_dict({k: (base[k].float() + A * (ft[k].float() - base[k].float())) if k in ft and base[k].is_floating_point() else base[k] for k in base})
    singer.cuda().eval()
    @part(f'{tag} で乱数6通り')
    def _gen():
        for nm in ALL:
            ref_latent, ref_len, text, total, midi_in, midi_p, bound_p = [x.cuda() if torch.is_tensor(x) else x for x in preps[nm]]
            for sd in SEEDS:
                with torch.inference_mode():
                    g, _ = singer.sample(cond=ref_latent, midi_in=midi_in, text=text, duration=total, steps=32, cfg_strength=3.0, sway_sampling_coef=None,
                                         use_epss=False, seed=sd, midi_p=midi_p, t_shift=0.5, bound_p=bound_p, guidance_scale=3.0)
                lat = g.float()[:, ref_len:-int(44100 / 2048 * 1.0), :].permute(0, 2, 1)
                dec_save(lat, f'{OUT}/gen/{nm}_{tag}_chg_s{sd}.wav')
            print('歌わせた', tag, nm, flush=True)
    if not CAPS:   # 本物の入力をつかまえる（1段だけ）。α によらず同じ
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
            CAPS[nm] = (cap, ref_len)
        singer.transformer.forward = orig
    @part(f'{tag} の ONNX（q4b32）')
    def _dit():
        from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer
        step = Step(singer.transformer.float().cpu()).eval(); c0 = CAPS['momo'][0]
        f32 = f'{OD}/dit_{tag}_f32.onnx'
        with torch.no_grad():
            torch.onnx.export(step, (c0['x'], c0['cond'], c0['text'], c0['midi'], c0['time']), f32, input_names=['x', 'cond', 'text', 'midi', 't'], output_names=['v'],
                              opset_version=18, dynamo=False, dynamic_axes={'x': {1: 'n'}, 'cond': {1: 'n'}, 'text': {1: 'nt'}, 'midi': {1: 'n'}, 'v': {1: 'n'}})
        p = f'{OD}/dit_{tag}_q4b32.onnx'
        q = MatMulNBitsQuantizer(f32, bits=4, block_size=32, is_symmetric=True, accuracy_level=4); q.process(); q.model.save_model_to_file(p, True)
        for f in os.listdir(OD):
            if f.startswith(f'dit_{tag}_f32'): os.remove(f'{OD}/{f}')
        DITQ[tag] = p
        singer.cuda()
    singer.cpu(); gc.collect(); torch.cuda.empty_cache()
REPORT['t_shape'] = list(CAPS['momo'][0]['time'].shape) if CAPS else None

# ---- ONNX だけで最初から最後まで（スマホと同じ道）----
@part('ONNX だけで通しで歌う')
def _e2e():
    se_e, se_m, se_d = sess(ENC), sess(MEL), sess(DEC)
    r = {}
    for tag, p in DITQ.items():
        se_t = sess(p)
        for nm in NAMES:
            cap, _ = CAPS[nm]; tm = {}
            w = mono44(WAV[nm]); rng = np.random.RandomState(7)
            t1 = time.time()
            mr, sr_ = se_e.run(None, {'audio': st(pad_sil(w, 0.5)).numpy()}); lr = mr + sr_ * rng.standard_normal(mr.shape).astype(np.float32)
            mm_, sm_ = se_e.run(None, {'audio': st(pad_sil(w, 1.0)).numpy()}); lm = mm_ + sm_ * rng.standard_normal(mm_.shape).astype(np.float32)
            tm['声→数字'] = round(time.time() - t1, 2)
            ref_len = lr.shape[2]; total = ref_len + lm.shape[2]
            tokens = np.load(f'{OUT}/phone/case_{nm}.npz')['tokens']
            assert tokens.shape[1] == total and total == cap['x'].shape[1], f'{nm} 長さ {tokens.shape} {total} {cap["x"].shape}'
            t1 = time.time()
            midi = se_m.run(None, {'ref_audio': pad_sil(w, 0.5)[None], 'mel_audio': pad_sil(w, 1.0)[None], 'grid': np.zeros((1, total), np.float32), 'ref_len': np.array([ref_len], np.int64)})[0]
            tm['メロディ'] = round(time.time() - t1, 2)
            cond = np.zeros((1, total, 64), np.float32); cond[0, :ref_len] = lr[0].T
            y = rng.standard_normal((1, total, 64)).astype(np.float32)
            ts = np.linspace(0, 1, 33); ts = (0.5 * ts / (1 + (0.5 - 1) * ts)).astype(np.float32)
            t1 = time.time()
            for k in range(32):
                v = se_t.run(None, {'x': y, 'cond': cond, 'text': tokens, 'midi': midi, 't': np.full(tuple(cap['time'].shape), ts[k], np.float32)})[0]
                y = y + (ts[k + 1] - ts[k]) * v
            tm['AI本体32段'] = round(time.time() - t1, 1)
            lat = np.ascontiguousarray(y[:, ref_len:-int(44100 / 2048 * 1.0), :].transpose(0, 2, 1))
            t1 = time.time(); a = se_d.run(None, {'latent': lat})[0]; tm['数字→声'] = round(time.time() - t1, 2)
            a = smooth_ending(torch.from_numpy(a[0]).float(), 44100)
            sf.write(f'{OUT}/e2e/{nm}_{tag}_onnxall.wav', a.numpy().T, 44100)
            tm['midiのずれ（torch と）'] = rel(midi, cap['midi'].numpy()); tm['歌詞の記号が同じ'] = bool((tokens == cap['text'].numpy()).all())
            r[f'{nm}_{tag}'] = tm; print('通しで歌った', nm, tag, tm, flush=True)
    REPORT['e2e_detail'] = r

json.dump(REPORT, open(f'{OUT}/report.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(REPORT, ensure_ascii=False, indent=1))
zp = shutil.make_archive(f'{OUTD}/kp_parts_out_v1', 'zip', OUT)
for f in os.listdir(OD):
    if f.endswith('.onnx') or '.onnx.' in f: shutil.copy(f'{OD}/{f}', OUTD)
print('完了：右の「Output」の kp_parts_out_v1.zip を送ってください（.onnx はスマホ用。あとで案内します）', flush=True)
