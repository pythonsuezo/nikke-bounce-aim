# Nikke Bounce Aim

NIKKE ミニゲーム向けボール反射軌道オーバーレイ（Windows）。

## ダウンロード（exe）

最新版はこちらからどうぞ：

**[Releases / ダウンロード](https://github.com/pythonsuezo/nikke-bounce-aim/releases/latest)**

zip の中身：

- `NikkeBounceAim.exe` … 本体（ダブルクリックで起動）
- `取説.txt` … 操作説明

Python のインストールは不要です。詳しい使い方は zip 内の `取説.txt`、またはリポジトリの [`取説.txt`](./取説.txt) を見てください。

## 開発用起動

```powershell
py -3 -m pip install -r requirements.txt
py -3 main.py
```

または `run.bat`

## exe を自分でビルドする場合

```powershell
.\build_exe.bat
```

出力先: `dist\NikkeBounceAim_配布\`
