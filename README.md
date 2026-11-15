<p align="center"><img src="logo.png" width="180" alt="KazuPlayer"></p>

<h1 align="center">KazuPlayer</h1>

<p align="center">自分で作った曲を、聴く・比べる・確かめる・仕上げる・公開する。<br>AIで曲を作る人のための、Android用の音楽・動画プレイヤー（無料・趣味で作っています）。</p>
<p align="center">A free Android music &amp; video player for people who make songs, including with AI (a hobby project).</p>
<p align="center"><b>Sunoの曲の1語だけ、作り直さずに同じ声のまま直す / Fix one mispronounced word in a Suno song — without regenerating, same voice</b></p>

<p align="center"><b><a href="https://kazusato-japan.github.io/KazuPlayer/">紹介ページ / Website</a></b> ・ <b><a href="https://kazusato-japan.github.io/KazuPlayer/manual.html">使い方マニュアル / User manual</a></b> ・ <a href="https://github.com/kazuSato-Japan/KazuPlayer/releases/latest/download/KazuPlayer.apk">ダウンロード / Download (KazuPlayer.apk)</a></p>

[日本語](#日本語) ・ [English](#english)

---

## 日本語

### できること
- **歌の部分修正**：Suno などで作った曲の「1文字だけ発音や読みが違う」所を、作り直さずにスマホの中で直します。歌詞と歌声を1文字ずつ比べて違って聞こえる所を探し、同じ曲の中で同じ歌手が歌っている音を借りて差し替えます。正しい歌詞で1行だけ歌い直すこともできます。日本語・英語に対応
  - 聴き比べ（直す前 → 直した後）：[「蟻」が「まり」に聞こえていた所](samples/ari_before_after.mp3) ・ [「腿」を「たい」と読んでいた所](samples/momo_before_after.mp3) ・ [英語 rifts → drifts](samples/english_before_after.mp3) ・ [YouTube（22秒）](https://youtu.be/zOCYKqtx2EY)
- **傷・音量の直し**：Suno などの曲によくある、1秒もない小さな傷（プチッ・カチッという音、音が一瞬消える所）を自動で探して直します。気になった所だけ、全部の音か1つのパート（歌・ベース・ドラム・その他）の音量を上げ下げしたり、くり返しの同じ所から借りて貼ったりもできます。歌詞・楽譜は要りません
- **楽譜（自動採譜・試作）**：メロディ（歌詞付き）・コーラス・ギター/鍵盤・ベース・ドラム。PDF・MIDI。音符の高さ・長さも曲の音ごと直せます
- **マスタリング**：ジャンル・雰囲気かお手本の曲を選んで仕上げ、元の音と聴き比べてから書き出し
- **バージョン聴き比べ・音の診断・聞こえ方チェック・お手本と比べる**
- **歌詞を仕上げる**：自動で時刻付け（LRC）、タップで同期、埋め込み、字幕(.srt)、歌詞動画
- **公開準備・作品カード**
- **プレイヤー**：10バンドEQ、ReplayGain、動画・YouTube の小窓再生、日本語/英語の画面

機能ごとの詳しい使い方は[使い方マニュアル](https://kazusato-japan.github.io/KazuPlayer/manual.html)へ。

### よくある質問
- **Sunoで作った曲の1語だけ、ボーカルを変えずに直せますか？** 発音や読みが違う・聞き取りにくい1語なら直せます。Sunoで作り直すと声や歌い方まで変わりますが、KazuPlayerはダウンロードした曲そのものを直します。同じ曲の中で同じ歌手がうまく歌えている音を借りて、その所だけ差し替えます
- **全く別の言葉に変えられますか？** その音が曲の中のどこにも無い言葉には変えられません（例：cat → dog）。正しい歌詞で1行だけ歌い直す機能か、Sunoの置き換えを使ってください
- **Sunoの曲の「プチッ」「カチッ」や、一瞬音が消える所は直せますか？** 直せます。「作る」タブの「傷・音量の直し」で「傷を探す」を押すと、曲全体から探して並べます。聴いて選んで直します（元の曲は残します）
- **お金やクレジットはかかりますか？** かかりません。Sunoのクレジットも使わず、曲はスマホの外に送りません

### できないこと・注意
- 部品が大きいです（楽譜と歌の部分修正で約1.9GB、歌い直しのAIで約1.8GB。使う分だけで足ります）
- 処理が重く、スマホが温かくなります（楽譜の上位版は4分の曲で30分ほど）
- 歌と伴奏、メインとコーラスは完全には分けられず、直した所に元の音が少し残ることがあります
- 自動なので、指摘や楽譜が間違うことがあります
- 楽譜・歌の部分修正・書き出しなどは、インターネットにつながっている所で使えます（曲は外に送りません）

### インストール
1. 上のリンクから `KazuPlayer.apk` をダウンロードして開きます（Android 11以降）
2. 「この提供元のアプリを許可」をオンにしてインストールします。途中の警告の説明は[紹介ページ](https://kazusato-japan.github.io/KazuPlayer/#install-warning)にあります

### プライバシー・利用条件
アカウント・広告はありません。曲ファイルを外に送ることはありません。個人での利用は自由（無料）です。アプリの再配布、改変した版の配布、中身を取り出しての転載はお断りします。配布はこのページ（GitHub）だけです。

---

## English

### What it does
- **Vocal fix**: fix the one word that came out wrong in a Suno (or other AI) track, on your phone, without regenerating. The app compares the singing with your lyrics syllable by syllable, finds what sounds off, and replaces just that sound with the same singer’s take from elsewhere in the same song. You can also re-sing a single line with the correct lyrics. English and Japanese
  - Before → after: [English: “rifts” → “drifts”, “fold” → “Hold”](samples/english_before_after.mp3) ・ [Japanese 1](samples/ari_before_after.mp3) ・ [Japanese 2](samples/momo_before_after.mp3) ・ [YouTube demo (22 s)](https://youtu.be/zOCYKqtx2EY)
- **Glitch & volume fix**: automatically finds and fixes the tiny glitches under a second that are common in Suno songs — clicks, ticks and split-second dropouts. Raise or lower the volume of just one spot (whole mix or one part: vocals, bass, drums, other), or patch a spot from a repeat. No lyrics or score needed
- **Sheet music (beta)**: melody with lyrics, chorus, guitar/keys, bass, drums. PDF and MIDI. Fix a note’s pitch or length in the audio too
- **Mastering**: pick a genre, mood or reference track, compare with the original, then export
- **Version comparison, sound check, listening simulator, reference comparison**
- **Lyrics**: auto-timing (LRC), tap sync, embedding, subtitles (.srt), lyric videos
- **Release prep and work cards**
- **Player**: 10-band EQ, ReplayGain, video and YouTube picture-in-picture, English/Japanese UI

Every feature in detail: [user manual](https://kazusato-japan.github.io/KazuPlayer/manual.html?lang=en).

### FAQ
- **Can I change one word in a Suno song without changing the vocals?** Yes, if the word is mispronounced, slurred or hard to hear. Regenerating in Suno changes the voice and phrasing too; KazuPlayer fixes the downloaded song itself, borrowing the same sound from a spot in the same song where the same singer sang it well.
- **Can I turn a word into a completely different word?** Not if those sounds don’t exist anywhere in the song (e.g. cat → dog). Use the re-sing-one-line feature or Suno’s Replace for that.
- **Can it fix clicks, ticks and split-second dropouts in a Suno song?** Yes. In the Create tab, open “Glitch & volume fix” and tap “Find glitches”; it scans the whole song and lists them. Listen, pick and fix (the original is kept).
- **Does it cost money or Suno credits?** No. It is free, uses no Suno credits, and your songs never leave your phone.

### Limitations
- Large downloads (about 1.9GB for sheet music and vocal fix, about 1.8GB for the re-singing AI — only what you use)
- Heavy processing; your phone gets warm (advanced sheet music takes about 30 minutes for a 4-minute song)
- Vocals and backing, lead and chorus can’t be separated perfectly, so a little of the original may remain where you fixed
- It’s automatic, so it can make mistakes
- Sheet music, vocal fix and export need an internet connection (your songs are not uploaded)

### Install
1. Download `KazuPlayer.apk` from the link above and open it (Android 11+)
2. Turn on “Allow from this source” and install. The install warnings are explained on the [website](https://kazusato-japan.github.io/KazuPlayer/#install-warning)

### Privacy and terms
No account, no ads. Your song files are never uploaded. Personal use is free. Redistributing the app, distributing modified versions, or extracting and republishing its contents is not allowed. The app is distributed only from this page (GitHub).
