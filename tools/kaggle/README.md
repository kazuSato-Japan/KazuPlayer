# Kaggle 用（歌い直しAIの部品づくり）
Kaggle のノートのセルは下の固定の3行だけ。中身はここ（run.py → JOB.txt に書いた jobs/*.py）を毎回取ってくる。
```
WLINK = '（重みの共有リンク）'
import urllib.request as u
exec(u.urlopen(u.Request('https://api.github.com/repos/kazuSato-Japan/KazuPlayer/contents/tools/kaggle/run.py?ref=main', headers={'Accept':'application/vnd.github.raw','User-Agent':'kazuplayer-kaggle'})).read().decode())
```
