# EEW Alert HA

このHome Assistantインテグレーションは[EEW Alert for Home Assistant](https://github.com/kotarou2211/ha-eew-alert)のforkです。
元のコードにはChromecastへの警告画像のキャスト、照明や鍵の制御などの機能が含まれています。本forkではChromecast関連の機能を取り除き、警報はHome Assistant eventが発行されます。
このため警報発令時の機器の制御はユーザがHome Assistantのautomationで記述します。

## 元のrepositoryから取り除かれた機能

- Chromecastのサポート
- 警報発令時の照明の制御
- 警報発令時の鍵の制御
- 在宅情報によるフィルタリング
- 震度マップの生成
  
## 特徴

- P2P地震情報のWebSocketに直接接続（追加のミドルウェアなし）
- 閾値震度・監視対象都道府県を設定画面（Config Flow）から設定可能
- 対象地域で閾値以上の震度の警報が発令された場合、Home Assistant eventが発行される
- 訓練・試験配信を無視するかどうかを設定可能
- 動作確認用の「テスト送信」ボタンを提供

## インストール

### HACS経由（カスタムリポジトリ）

1. HACS → Integrations → 右上のメニュー → Custom repositories
2. このリポジトリのURLを追加し、カテゴリは「Integration」を選択
3. `EEW Alert HA` を検索してインストール
4. Home Assistantを再起動

### 手動インストール

1. `custom_components/eew_alert_ha` を Home Assistantの `config/custom_components/` 配下にコピー
2. Home Assistantを再起動

## 設定

Home Assistant → 設定 → デバイスとサービス → 統合を追加 → `EEW Alert HA` を検索し、画面の指示に従って設定します。

主な設定項目:

| 項目 | 説明 |
|---|---|
| 閾値震度 | この震度以上でイベントを発行 |
| 対象都道府県 | 指定した場合、指定した地域の震度を基準に判定（複数指定可。未指定なら全国最大震度で判定） |
| 訓練・試験配信を無視 | ONの場合、P2P地震情報の訓練・試験電文は無視 |

## イベントの詳細

警報発令により以下のeventが発行される。``prefs` には設定した対象都道府県ごとの予想震度が含まれます。

```
event_type: eew_alert_triggered
data:
  id: test
  scale: 50
  label: 5強
  hypocenter: テスト震源
  prefs:
    - pref: 東京都
      scale: 50
  origin: LOCAL
```

なお、`scale`は震度の10倍で、`label`との関係は以下の表の通りです。
| scale | 震度 |
|---:|---|
| 10 | 1 |
| 20 | 2 |
| 30 | 3 |
| 40 | 4 |
| 45 | 5弱 |
| 50 | 5強 |
| 55 | 6弱 |
| 60 | 6強 |
| 70 | 7 |

## 動作確認

`button.テスト送信` を押すと、実際のWebSocket受信をスキップしてダミーデータで生成されるトリガーを検証できます。

実際の受信パイプライン全体（WebSocket受信→パース→反応）を検証したい場合は、「訓練・試験配信を無視する」設定を一時的にOFFにし、P2P地震情報が定期的に配信する訓練・試験電文を待つ方法が確実です。

## ライセンス

MIT License

同梱の日本語フォント（NotoSansJP.ttf）は [SIL Open Font License 1.1](https://openfontlicense.org/) の下で配布されています。

## 免責事項

本ソフトウェアは有志による非公式のツールであり、気象庁や地震予知連絡会等の公式な緊急地震速報システムを代替するものではありません。本ソフトウェアの動作不良や情報の遅延・誤りにより生じたいかなる損害についても、作者は責任を負いません。
