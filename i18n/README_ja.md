<div align="center">
  <p>
    <img alt="Track Studio" src="../assets/banner.svg" width="80%" height="200">
  </p>
</div>

<div align="center">

[![Python Linting & Code Quality](https://github.com/playbox-dev/trackstudio/actions/workflows/lint.yml/badge.svg)](https://github.com/playbox-dev/trackstudio/actions/workflows/lint.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](../LICENSE)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

<h4 align="center">
    <p>
        <a href="../README.md">English</a> |
        <b>日本語</b> |
    </p>
</h4>

## Track Studioとは？

**ライブ配信用のマルチカメラ・マルチオブジェクト追跡システム**

WebRTCストリーミング、コンピュータビジョン統合、Bird's Eye View（BEV）変換機能を備えたリアルタイムマルチカメラオブジェクト検出・追跡システムです。モジュール式で拡張可能な設計により、独自のトラッカーやマージャーを簡単に追加できます。

![Dashboard](../assets/overview.gif)

## 機能

- 🎥 **マルチカメラサポート** - 複数のRTSPストリームを同時処理
- 🤖 **検出と追跡** - デフォルトでRFDETR検出とDeepSORT追跡を使用
- 🌐 **WebRTCストリーミング** - 低遅延ブラウザベース表示
- 🎯 **クロスカメラマージング** - 複数のカメラビュー間でオブジェクトを追跡
- 🏗️ **拡張可能** - カスタムトラッカーとマージャー用のプラグインシステム
- 🚀 **使いやすい** - シンプルなPython API

## 要件

- Python 3.10+
- CUDA対応GPU（推奨）
- ハードウェアアクセラレーション対応のFFmpeg
- RTSPストリームまたはカメラ

## インストール

```bash
# GitHubからインストール
pip install git+https://github.com/playbox-dev/trackstudio.git
```

開発用:
```bash
git clone https://github.com/playbox-dev/trackstudio
cd trackstudio
pip install -e .
# またはuvを使用する場合（推奨）
uv sync --dev
```

## Thinklet Cubeを使用する場合
Thinklet Cubeは、WiFiまたは4G LTEを使用してメディアサーバにストリーミングできる小型で高耐久性、低消費電力のデバイスです。詳細については[Fairy Devices](https://mimi.fairydevices.jp/technology/device/thinklet_cube/)をご覧ください。
本設定では、Thinklet CubeをWiFi接続経由でローカルネットワーク上のMediaMTXサーバーにRTMPでビデオストリーミングするために使用します。同じWiFiネットワークに接続された2台以上のThinklet Cube、Thinklet Cubeに接続するためのadb、GPUを搭載したPCが必要です。adbのインストールとThinklet Cubeへの接続に関する詳細な手順は[Thinklet Developer Portal](https://fairydevicesrd.github.io/thinklet.app.developer/docs/startGuide/startGuide)にあります。

### 手順
```bash
# 1. MediaMTXサーバーを開始
docker compose up -d mediamtx

# 2. Thinklet CubeをPCに接続し、これらのコマンドを実行してMediaMTXサーバーへのビデオストリーミングを開始
adb -s <camera0のデバイスID（adb devicesで表示）> shell am start \
    -n ai.fd.thinklet.app.squid.run/.MainActivity \
    -a android.intent.action.MAIN \
    -e streamUrl "rtmp://<サーバーIP>:1935" \
    -e streamKey "camera0" \
    --ei longSide 720 \
    --ei shortSide 480 \
    --ei videoBitrate 1024 \
    --ei audioSampleRate 44100 \
    --ei audioBitrate 128 \
    --ez preview false

adb -s <camera1のデバイスID（adb devicesで表示）> shell am start \
    -n ai.fd.thinklet.app.squid.run/.MainActivity \
    -a android.intent.action.MAIN \
    -e streamUrl "rtmp://<サーバーIP>:1935" \
    -e streamKey "camera1" \
    --ei longSide 720 \
    --ei shortSide 480 \
    --ei videoBitrate 1024 \
    --ei audioSampleRate 44100 \
    --ei audioBitrate 128 \
    --ez preview false

# 3. ストリーミング開始: Thinklet Cubeの中央ボタンを押してストリーミングを開始

# 4. テスト設定でTrackStudioを実行
trackstudio run -c test_config.json --vision-fps 10

# 5. ブラウザでhttp://localhost:8000を開く
```

## ローカルでのテスト

実際のカメラなしでテストする場合は、ffmpegを使用してRTSPテストストリームを配信します：
`tests/videos`ディレクトリ内に`cam1.mp4`と`cam2.mp4`という名前の2つのビデオがあることを前提としています。`stream_camera0_ffmpeg.sh`と`stream_camera1_ffmpeg.sh`スクリプトでビデオファイルを変更できます。
[Large Scale Multi-Camera Tracking Dataset](https://www.kaggle.com/datasets/aryashah2k/large-scale-multicamera-detection-dataset) [1]のビデオでテストしました。

```bash
# 1. MediaMTXサーバーを開始
docker compose up -d mediamtx

# 2. テストストリームを作成
./test_mediamtx.sh

# 3. テスト設定でTrackStudioを実行
trackstudio run -c test_config.json

# 4. ブラウザでhttp://localhost:8000を開く
```

これにより、以下に2つのテストストリームが作成されます：
- `rtsp://localhost:8554/camera0`
- `rtsp://localhost:8554/camera1`

停止するには: `docker compose down`

## 🚀 クイックスタート

### Python API

```python
import trackstudio as ts

# デフォルト設定で起動
app = ts.launch()

# カスタム設定
app = ts.launch(
    rtmp_streams=[
        "rtsp://localhost:8554/camera0",
        "rtsp://localhost:8554/camera1"
    ],
    camera_names=["Camera 0", "Camera 1"],
    tracker="rfdetr",
    server_port=8000,
)
```

### コマンドライン

```bash
# デフォルト設定でサーバーを開始
trackstudio run

# カスタムストリームで開始
trackstudio run --streams rtsp://localhost:8554/camera0 rtsp://localhost:8554/camera1

# 設定ファイルを生成
trackstudio config --output my_config.json

# 利用可能なコンポーネントをリスト表示
trackstudio list
```

## 設定

TrackStudioは以下の方法で設定できます：
- Python APIパラメータ
- コマンドライン引数
- JSON設定ファイル

設定ファイルの例：
```json
{
  "cameras": {
    "stream_urls": [
      "rtsp://localhost:8554/camera0",
      "rtsp://localhost:8554/camera1"
    ]
  },
  "vision": {
    "tracker_type": "rfdetr",
    "merger_type": "bev_cluster",
    "fps": 10.0
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

## 独自トラッカー

自動登録機能付きの独自トラッカーを作成 - **既存のファイルを変更する必要はありません！**

### ステップ1: トラッカー設定を作成

```python
from trackstudio.vision_config import register_tracker_config, BaseTrackerConfig, slider_field
from pydantic import Field

@register_tracker_config("mytracker")  # システムに自動登録！
class MyTrackerConfig(BaseTrackerConfig):
    """私のカスタムトラッカーの設定"""
    detection_threshold: float = slider_field(
        0.5, 0.1, 1.0, 0.1,
        "検出閾値",
        "検出がどの程度確信的である必要があるか"
    )
    max_tracks: int = Field(default=50, title="最大追跡数")
```

### ステップ2: トラッカークラスを作成

```python
from trackstudio.tracker_factory import register_tracker_class
from trackstudio.trackers.base import VisionTracker
import numpy as np

@register_tracker_class("mytracker")  # ファクトリに自動登録！
class MyTracker(VisionTracker):
    def __init__(self, config: MyTrackerConfig):
        super().__init__(config)
        self.config = config

    def detect(self, frame: np.ndarray, camera_id: int):
        # ここに検出ロジックを記述
        detections = []
        return detections

    def track(self, detections, camera_id: int, timestamp: float, frame=None):
        # ここに追跡ロジックを記述
        tracks = []
        return tracks
```

### ステップ3: トラッカーを使用

```python
# 以上です！トラッカーがシステム全体で利用可能になりました
app = ts.launch(tracker="mytracker")
```
独自トラッカーの実装例は[custom_tracker_examples/demo.py](custom_tracker_examples/demo.py)にあります。

## アーキテクチャ

TrackStudioはモジュラーアーキテクチャを使用しています：

- **ビジョンパイプライン**: 検出 → 追跡 → BEV変換 → クロスカメラマージング
- **ストリーミング**: RTMP入力 → ハードウェアアクセラレーション付きWebRTC出力
- **Web UI**: リアルタイム可視化機能付きのReactベースインターフェース
- **プラグインシステム**: 独自トラッカーとマージャーの登録

## ロードマップ

- 追跡軌跡の可視化
- BEVキャンバスと入力カメラストリームでのハードコードされた画像とキャンバスサイズの除去
- 追跡データを使用したアプリケーション
- 検出クラスの処理
- クラウド展開ガイド

## コントリビューション

コントリビューションを歓迎します！

開発者向け：
- 📋 **[開発ガイド](../DEVELOPMENT.md)** - セットアップ、リンティング、コード品質ツール
- 🧹 **コード品質**: リンティングとフォーマットに[Ruff](https://docs.astral.sh/ruff/)を使用
- 🔧 **クイックセットアップ**: `make dev-setup`を実行して開始
- ✅ **プリコミットフック**: コミット時の自動コード品質チェック

## 参考文献

[1] [Large Scale Multi-Camera Tracking Dataset](https://www.kaggle.com/datasets/aryashah2k/large-scale-multicamera-detection-dataset)

[2] [RF-DETR](https://github.com/roboflow/rf-detr)

[3] [DeepSORT: Simple Online and Realtime Tracking with a Deep Association Metric](https://arxiv.org/abs/1703.07402)

## ライセンス

TrackStudioはApache License 2.0の下でライセンスされています。詳細は[LICENSE](../LICENSE)をご覧ください。

## 引用

研究でTrackStudioを使用する場合は、以下のように引用してください：

```bibtex
@software{trackstudio,
  title = {TrackStudio: Multi-Camera Vision Tracking System},
  author = {Playbox},
  year = {2025},
  url = {https://github.com/playbox-dev/trackstudio}
}
```

## サポート

- 📧 メール: support@play-box.ai
- 🐛 問題報告: [GitHub Issues](https://github.com/playbox-dev/trackstudio/issues)

## 🔗 リンク

- [ドキュメント](https://trackstudio.readthedocs.io/) # Coming soon
- [Thinklet Cube](https://mimi.fairydevices.jp/technology/device/thinklet_cube/)
- [PyPIパッケージ](https://pypi.org/project/trackstudio/)
- [GitHubリポジトリ](https://github.com/playbox-dev/trackstudio)
- [サンプルノートブック](https://github.com/playbox-dev/trackstudio/tree/main/examples) # Coming soon

---
