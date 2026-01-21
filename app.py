from flask import Flask, render_template, request, session, redirect, url_for, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import os
import json
import csv
from io import BytesIO

# 加点要素：追加モジュール（環境に無い場合でも動作するように try/except）
try:
    import pandas as pd
except Exception:
    pd = None

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as _fm

    def _configure_matplotlib_japanese():
        """日本語の文字化け（豆腐）を避けるためのフォント設定。
        - プロジェクト内の static/fonts 配下に日本語フォント(ttf/otf)があれば優先利用
        - 無ければOSに入っている可能性が高い日本語フォント名を順に試す
        """
        # 1) 同梱フォント（任意）を優先
        local_candidates = [
            os.path.join(app.root_path, "static", "fonts", "ipaexg.ttf"),
            os.path.join(app.root_path, "static", "fonts", "ipag.ttf"),
            os.path.join(app.root_path, "static", "fonts", "NotoSansJP-Regular.otf"),
            os.path.join(app.root_path, "static", "fonts", "NotoSansCJKjp-Regular.otf"),
        ]
        for fp in local_candidates:
            if os.path.exists(fp):
                try:
                    _fm.fontManager.addfont(fp)
                    prop = _fm.FontProperties(fname=fp)
                    matplotlib.rcParams["font.family"] = prop.get_name()
                    matplotlib.rcParams["axes.unicode_minus"] = False
                    return True
                except Exception:
                    pass

        # 2) システムフォント名（環境差があるので複数候補）
        name_candidates = [
            "IPAexGothic",
            "IPAGothic",
            "Noto Sans CJK JP",
            "Noto Sans JP",
            "TakaoGothic",
            "Yu Gothic",
            "Meiryo",
            "Hiragino Sans",
            "MS Gothic",
        ]
        for name in name_candidates:
            try:
                _fm.findfont(name, fallback_to_default=False)
                matplotlib.rcParams["font.family"] = name
                matplotlib.rcParams["axes.unicode_minus"] = False
                return True
            except Exception:
                continue

        matplotlib.rcParams["axes.unicode_minus"] = False
        return False

    # 追加モジュール（任意）：入っていれば一発で日本語フォントを設定してくれる
    try:
        import japanize_matplotlib  # noqa: F401
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass

except Exception:
    plt = None


app = Flask(__name__)
# session を使うために secret_key を設定
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change_me_secret_key')

# ---- 種データ（出典は各種の sources を参照） ----
SPECIES = [
    {
        'id': 'delphinapterus_leucas',
        'jp': 'シロイルカ',
        'en': 'Beluga whale',
        'sci': 'Delphinapterus leucas',
        'family': 'イッカク科（Monodontidae）',
        'length': '最大16 ft（約4.9 m）',
        'weight': '平均3,150 lb（約1,430 kg）',
        'lifespan': '最大90年',
        'distribution': '北半球の北極海と周辺海域に分布し、アラスカの多くの海域のほか、ロシア、カナダ、グリーンランドにも見られる。\n夏は浅い沿岸の浅瀬に多いが、季節によってはより深い海域にも移動し、最大で水深1,000 mまで潜水し、最長25分の潜水が報告されている。\n河口域や大きな河川デルタにも季節的に入り、魚の遡上（魚群）を利用して採餌する。',
        'ecology': '「海のカナリア」とも呼ばれ、口笛・鳴き声・クリックなど多様な音を出す。聴覚とエコーロケーション（反響定位）で移動・採餌を行う。\n食性は多様で、タコ・イカ・カニ・エビ・二枚貝・巻貝・ゴカイ類などの無脊椎動物に加え、サケ、ユースタキオン（eulachon）、タラ、ニシン、ワカサギ類、カレイ類などの魚類も食べる。\n交尾は主に晩冬〜春とされ、雌は6〜14歳頃、雄はそれよりやや遅く性成熟する。妊娠期間は約15か月で、仔は少なくとも2年間授乳する。出産は一般に夏（新生仔の保温に有利な比較的温暖な海域）に多く、出産間隔は2〜3年とされる。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Beluga Whale',
                'url': 'https://www.fisheries.noaa.gov/species/beluga-whale'
            }
        ]
    },
    {
        'id': 'monodon_monoceros',
        'jp': 'イッカク',
        'en': 'Narwhal',
        'sci': 'Monodon monoceros',
        'family': 'イッカク科（Monodontidae）',
        'length': '13–18 ft（約4.0–5.5 m）',
        'weight': '1,760–3,530 lb（約800–1,600 kg）',
        'lifespan': '最大50年',
        'distribution': '北極海およびその周辺海域（大西洋側の北極域）に分布する。',
        'ecology': '主な餌はグリーンランドオヒョウ（Greenland halibut）やホッキョクダラ（Arctic cod）で、イカやエビも食べるとされる。\n最大で3,937 ft（約1,200 m）まで潜水し、最長25分程度の潜水が報告されている。\n妊娠期間は13〜16か月とされ、通常1頭の仔を出産する。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Narwhal',
                'url': 'https://www.fisheries.noaa.gov/species/narwhal'
            }
        ]
    },
    {
        'id': 'orcinus_orca',
        'jp': 'シャチ',
        'en': 'Killer whale (Orca)',
        'sci': 'Orcinus orca',
        'family': 'マイルカ科（Delphinidae）',
        'length': '23–32 ft（約7.0–9.8 m）',
        'weight': '8,000–12,000 lb（約3,600–5,400 kg）',
        'lifespan': '雄：平均約30年（最大で少なくとも60年）／雌：平均約50年（最大で少なくとも90年）',
        'distribution': '全ての海に分布する。南極・ノルウェー・アラスカなどの寒冷海域で個体数が多い一方、熱帯・亜熱帯にも見られる。\n北東太平洋では、定住型（Resident）はカリフォルニアからロシアまで観察され、沖合型（Offshore）は沖合9マイル（約14 km）以遠にも多いとされる。',
        'ecology': '高い社会性をもち、母系血縁を基盤とする「ポッド（pod）」と呼ばれる社会集団で生活する。\n水中音を利用して採餌・コミュニケーション・航行を行い、クリック・ホイッスル・パルス音などを用いる。北東太平洋の各ポッドは学習により共有される固有のコール（鳴音セット）をもつ。\n食性は生息海域の餌資源だけでなく、生態型（ecotype）ごとに学習された採餌文化に強く依存する。例えば米国太平洋岸北西部では、魚食（主にサケ）に特化する集団と、海棲哺乳類やイカを主に食べる集団が知られる。\n雌は10〜13歳で性成熟し、妊娠期間は15〜18か月、通常1頭の仔を出産する。仔は少なくとも1年間は母乳栄養のみで、その後も母親と密接に行動する期間が続く。出産季節は明確ではなく、出生は通年で起こりうる。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Killer Whale',
                'url': 'https://www.fisheries.noaa.gov/species/killer-whale'
            }
        ]
    },
    {
        'id': 'tursiops_truncatus',
        'jp': 'ハンドウイルカ',
        'en': 'Common bottlenose dolphin',
        'sci': 'Tursiops truncatus',
        'family': 'マイルカ科（Delphinidae）',
        'length': '6–13 ft（約1.8–4.0 m）',
        'weight': '300–1,400 lb（約140–640 kg）',
        'lifespan': '',
        'distribution': '世界の温帯〜熱帯域に広く分布する。\n港湾・湾・内海・河口域などの沿岸環境に加え、大陸棚上のやや深い海域、さらに外洋の沖合まで、多様な環境で確認されている。',
        'ecology': '単独または群れで行動し、群れは分裂・再編を繰り返す（いわゆるフィッション・フュージョン型）。\n魚類・イカ・甲殻類（カニやエビなど）など多様な餌を利用し、単独採餌だけでなく協調して魚群を追い込むなど複数の採餌戦略を用いる。\n高周波のエコーロケーション等を用いて獲物を探索し、歯で魚を把持して頭から丸呑みする。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Common Bottlenose Dolphin',
                'url': 'https://www.fisheries.noaa.gov/species/common-bottlenose-dolphin'
            }
        ]
    },
    {
        'id': 'phocoena_phocoena',
        'jp': 'ネズミイルカ',
        'en': 'Harbor porpoise',
        'sci': 'Phocoena phocoena',
        'family': 'ネズミイルカ科（Phocoenidae）',
        'length': '5–5.5 ft（約1.5–1.7 m）',
        'weight': '135–170 lb（約61–77 kg）',
        'lifespan': '最大24年',
        'distribution': '北半球の温帯北部〜亜寒帯・北極域の沿岸〜沖合に分布する。湾・河口・港・フィヨルドなど水深650 ft（約200 m）未満の海域でよく見られる。\n北大西洋では西グリーンランド〜米国ノースカロライナ州ケープハッテラス付近、またバレンツ海〜西アフリカにかけて分布し、北太平洋では日本〜チュクチ海、米国カリフォルニア州ポイント・コンセプション〜ボーフォート海まで分布するとされる。',
        'ecology': '主にニシンやサバなどの群れを作る魚類を食べ、時にイカ・タコも食べる。\n単独・ペア・10頭程度の小群で見られることが多いが、最大200頭規模の集合例も報告される。季節移動は沿岸—沖合方向の変化が中心で、餌資源や海氷条件の影響を受ける可能性がある。\n雌は3〜4歳で性成熟し、妊娠期間は10〜11か月、授乳は8〜12か月とされる。出産は主に5〜7月に多い。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Harbor Porpoise',
                'url': 'https://www.fisheries.noaa.gov/species/harbor-porpoise'
            }
        ]
    },
    {
        'id': 'megaptera_novaeangliae',
        'jp': 'ザトウクジラ',
        'en': 'Humpback whale',
        'sci': 'Megaptera novaeangliae',
        'family': 'ナガスクジラ科（Balaenopteridae）',
        'length': '最大60 ft（約18 m）',
        'weight': '最大80,000 lb（約36 t）',
        'lifespan': '推定約80〜90年',
        'distribution': '世界の主要な海に広く分布する。季節移動で高緯度の夏季採餌海域と、熱帯域の交尾・出産海域を往復し、個体によっては約5,000マイル（約8,000 km）を移動する。\n北太平洋ではアラスカ〜ハワイ間（約3,000マイル）を最短28日で移動した例がある。出産期には浅く温暖な海域（リーフ周辺や沿岸）を好むとされる。',
        'ecology': '採餌海域は一般に寒冷で生産性の高い海域とされる。\n性成熟は4〜10歳で、雌は平均して2〜3年に1回、1頭の仔を出産する。妊娠期間は約11か月で、出生仔の体長は約13〜16 ftとされる。仔は離乳まで最大1年程度、母親の近くで行動する。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Humpback Whale',
                'url': 'https://www.fisheries.noaa.gov/species/humpback-whale'
            }
        ]
    },
    {
        'id': 'balaenoptera_musculus',
        'jp': 'シロナガスクジラ',
        'en': 'Blue whale',
        'sci': 'Balaenoptera musculus',
        'family': 'ナガスクジラ科（Balaenopteridae）',
        'length': '最大110 ft（約34 m）',
        'weight': '最大330,000 lb（約150 t）',
        'lifespan': '推定約80〜90年',
        'distribution': '北極域を除くほぼ全ての海に分布する。\n一般に夏季は高緯度の採餌海域、冬季は繁殖海域へ季節移動するが、地域によっては移動しない個体群の可能性も示唆されている。分布と移動は餌（オキアミ等）の集中に強く影響される。\n北大西洋では亜熱帯〜グリーンランド海まで分布し、米国西海岸域では冬季にメキシコ〜中米沖、夏季に米国西海岸沖などでの採餌が示唆される。',
        'ecology': '単独またはペアで見られることが多いが、小規模な群れになることもある。採餌・移動時の遊泳速度はおよそ時速5マイル程度だが、短時間で20マイル以上まで加速できるとされる。\n主食はオキアミで、場合により魚類やカイアシ類（小型甲殻類）も食べる。口を開けてオキアミ群へ突進し、喉のヒダを膨らませて大量の海水ごと取り込み、ヒゲ板で濾し取る濾過摂食を行う。\n低周波のパルス・うなり声など非常に大きな音を発し、条件によっては1,000マイル離れた個体にも届きうるとされ、コミュニケーション等に用いられる可能性が示されている。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Blue Whale',
                'url': 'https://www.fisheries.noaa.gov/species/blue-whale'
            }
        ]
    },
    {
        'id': 'balaenoptera_physalus',
        'jp': 'ナガスクジラ',
        'en': 'Fin whale',
        'sci': 'Balaenoptera physalus',
        'family': 'ナガスクジラ科（Balaenopteridae）',
        'length': '最大80 ft（約24 m）',
        'weight': '最大100,000 lb（約45 t）',
        'lifespan': '',
        'distribution': '全ての主要な海の外洋性の深い海域に広く分布し、主に温帯〜極域で多い（熱帯では比較的少ない）。\n夏は極域寄りの採餌海域、冬は熱帯域の繁殖・出産海域へ移動する傾向があるが、冬季繁殖海域の位置は不明とされる。',
        'ecology': '高速で遊泳し、2〜7頭程度の群れで見られることが多い。北大西洋ではザトウクジラやミンククジラ等と混群で採餌する例もある。\n夏季はオキアミ、小型群泳魚（ニシン、カペリン、イカナゴ等）、イカ類を主に食べ、口を開けて獲物群へ突進し、喉のヒダで大量の海水ごと取り込み、ヒゲ板で濾し取る。\n冬季は移動期に入り、絶食するとされる。1日あたり最大2トンの餌を食べる例が記載されている。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Fin Whale',
                'url': 'https://www.fisheries.noaa.gov/species/fin-whale'
            }
        ]
    },
    {
        'id': 'balaenoptera_acutorostrata',
        'jp': 'ミンククジラ',
        'en': 'Minke whale',
        'sci': 'Balaenoptera acutorostrata',
        'family': 'ナガスクジラ科（Balaenopteridae）',
        'length': '最大35 ft（約11 m）',
        'weight': '最大20,000 lb（約9 t）',
        'lifespan': '',
        'distribution': '温帯〜亜寒帯（冷温帯）を好むが、熱帯・亜熱帯にも見られ、世界中の多くの海域で確認される（広域分布）。\n沿岸・内海から外洋の沖合まで利用し、季節移動するが、地域によっては定住的な個体群もあるとされる。',
        'ecology': '多くは単独または2〜3頭の小群で見られるが、極域寄りの採餌海域では最大400頭規模の疎な集合が観察された例がある。\n小魚群へ側方から突進して大量の海水ごと飲み込み、濾過摂食する。甲殻類・プランクトン・小型群泳魚（例：アンチョビー、タラ、ニシン、サケ、イカナゴ等）を機会的に利用する。\nクリック・グラントなど多様な音を発し、少なくとも15分の潜水が可能とされる。ブリーチングやスパイホッピングなど表層で活発な行動が見られる。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Minke Whale',
                'url': 'https://www.fisheries.noaa.gov/species/minke-whale'
            }
        ]
    },
    {
        'id': 'physeter_macrocephalus',
        'jp': 'マッコウクジラ',
        'en': 'Sperm whale',
        'sci': 'Physeter macrocephalus',
        'family': 'マッコウクジラ科（Physeteridae）',
        'length': '雌：40 ft（約12 m）／雄：52 ft（約16 m）',
        'weight': '雌：15トン／雄：45トン',
        'lifespan': '最大60年',
        'distribution': '世界の全ての海に分布する。分布は餌資源や繁殖に適した条件に依存し、群れの性・年齢構成によっても変化する。\nヒゲクジラ類ほど季節移動が予測しやすくはなく、成雄は温帯域まで長距離移動する一方、雌と若齢個体は熱帯域に周年分布する傾向が示されている。',
        'ecology': '日常的に水深2,000 ft（約610 m）に達する深潜水で採餌し、潜水は最大45分程度継続する。深潜水後は数分間の浮上休息を挟んで次の潜水に移る。\n深海性のイカ類、サメ類、エイ類、魚類などを食べるとされる。摂餌量は1日あたり体重の約3〜3.5%と記載されている。\n雌は約9歳・体長約29 ftで性成熟し、以後は5〜7年に1回程度の頻度で出産するとされる。妊娠期間は14〜16か月で、出生仔は約13 ft。仔は1年未満で固形物も食べ始めるが、授乳は数年続く。\n雄は成長が長く続き、身体的成熟は約50歳・体長約52 ftとされる。',
        'sources': [
            {
                'title': 'NOAA Fisheries: Sperm Whale',
                'url': 'https://www.fisheries.noaa.gov/species/sperm-whale'
            }
        ]
    },
    {
        'id': 'eubalaena_glacialis',
        'jp': 'セミクジラ（北大西洋個体群）',
        'en': 'North Atlantic right whale',
        'sci': 'Eubalaena glacialis',
        'family': 'セミクジラ科（Balaenidae）',
        'length': '最大52 ft（約16 m）',
        'weight': '',
        'lifespan': '',
        'distribution': '主に大西洋の大陸棚上の沿岸域に分布し、沖合の深海域まで移動することもある。\n季節移動を行い、春〜秋は米国ニューイングランド沖〜カナダ沿岸域で採餌・交尾し、秋以降に1,000マイル以上移動してサウスカロライナ〜ジョージア〜フロリダ北東部沖の浅い沿岸域（出産海域）へ向かう個体がいる（ただし移動パターンは変動する）。',
        'ecology': '水面でブリーチングするほか、口吻を水面上に出しながら高密度のプランクトンを「スキム・フィーディング（掬い取り型の濾過摂食）」で食べる行動が見られる。\n主食はカイアシ類（copepods）などの動物プランクトンで、ゆっくり泳ぎながら口を開けて取り込み、ヒゲ板で濾し取る。採餌は表層から水柱下部まで行われうる。\n水面での活発な社会行動（SAG）が観察され、交尾や社会的相互作用が起こる。低周波のうなり声・うめき声などでコミュニケーションするとされる。',
        'sources': [
            {
                'title': 'NOAA Fisheries: North Atlantic Right Whale',
                'url': 'https://www.fisheries.noaa.gov/species/north-atlantic-right-whale'
            }
        ]
    }
,

    {'id': 'lagenorhynchus_obliquidens',
     'jp': 'カマイルカ',
     'en': 'Pacific white-sided dolphin',
     'sci': 'Lagenorhynchus obliquidens',
     'family': 'マイルカ科（Delphinidae）',
     'length': '約1.7–2.4 m（5.5–8 ft）',
     'weight': '約136–181 kg（300–400 lb）',
     'lifespan': '36–40年（出典：NOAA Fisheries）',
     'distribution': '北太平洋の温帯域に分布し、外洋性（pelagic）。米国ではカリフォルニア～アラスカ沖で見られる。\n'
                     '北米以外では、ベーリング海南部（アリューシャン列島周辺）、オホーツク海、日本海、黄海・東シナ海（日本の南方を含む）などが挙げられる。',
     'ecology': '主にイカ類と小型の群泳魚（例：カペリン、イワシ類、ニシン類など）を食べる。\n潜水は6分以上続くことがあり、群れで魚群を追い込む行動が報告されている。成体は1日に約20 lbの餌を食べることがある。',
     'sources': [{'title': 'NOAA Fisheries: Pacific White-Sided Dolphin',
                  'url': 'https://www.fisheries.noaa.gov/species/pacific-white-sided-dolphin'}]},

    {'id': 'phocoenoides_dalli',
     'jp': 'イシイルカ',
     'en': "Dall's porpoise",
     'sci': 'Phocoenoides dalli',
     'family': 'ネズミイルカ科（Phocoenidae）',
     'length': '約2.1–2.4 m（7–8 ft）',
     'weight': '約200 kg（440 lb）',
     'lifespan': '15–20年（出典：NOAA Fisheries）',
     'distribution': '北太平洋の沿岸～外洋に広く分布し、深い海域（一般に水深600 ft超）と冷温帯～亜寒帯の水温（約36–63°F）を好む。\n'
                     '北緯30–62度の範囲で、アラスカ湾・ベーリング海・オホーツク海・日本海などに多い。米国ではバハ・カリフォルニア～ベーリング海、アジア側では日本中部～オホーツク海に分布するとされる。',
     'ecology': '最大で水深1,640 ftまで潜水し、群泳する小魚、深海性の魚（例：ハダカイワシ類・シシャモ類など）、頭足類を主に食べ、甲殻類を食べることもある。\n'
                '通常2–12頭程度の群れだが、時に数百～数千頭になる。カマイルカや短ヒレゴンドウクジラと混群を作ることがある。',
     'sources': [{'title': "NOAA Fisheries: Dall's Porpoise",
                  'url': 'https://www.fisheries.noaa.gov/species/dalls-porpoise'}]},

    {'id': 'stenella_longirostris',
     'jp': 'ハシナガイルカ',
     'en': 'Spinner dolphin',
     'sci': 'Stenella longirostris',
     'family': 'マイルカ科（Delphinidae）',
     'length': '約1.2–2.1 m（4–7 ft）',
     'weight': '約59–77 kg（130–170 lb）',
     'lifespan': '約20年（出典：NOAA Fisheries）',
     'distribution': '熱帯～暖温帯の海域に世界的に分布し、いくつかの亜種が知られる。\n一部個体群では沿岸の湾内などを日中の休息場所として利用し、夜間に外洋で採餌する。',
     'ecology': '夜間に深度650–1,000 ft付近で小魚・エビ類・イカ類などを捕食する。\n日中は4–5時間程度の休息行動をとり、休息中は主に視覚を用いる（エコーロケーションの使用は限定的とされる）。',
     'sources': [{'title': 'NOAA Fisheries: Spinner Dolphin',
                  'url': 'https://www.fisheries.noaa.gov/species/spinner-dolphin'}]},

    {'id': 'delphinus_delphis',
     'jp': 'マイルカ（短吻型）',
     'en': 'Short-beaked common dolphin',
     'sci': 'Delphinus delphis',
     'family': 'マイルカ科（Delphinidae）',
     'length': '約1.8 m（6 ft）',
     'weight': '約77 kg（170 lb）',
     'lifespan': '最大約40年（出典：NOAA Fisheries）',
     'distribution': '亜熱帯～温帯の外洋性で、一般に大陸棚縁辺・大陸斜面の海域（約300–6,500 ft）を好む。\n海流（例：ガルフストリーム）や湧昇域・海嶺などの生産性が高い海域と結び付くことがある。',
     'ecology': '数百頭規模の大きな群れを作り、時に約10,000頭の“メガポッド”になることがある。\n'
                '昼間は休息し、夜間に餌（群泳魚や頭足類）を探す傾向がある。潜水は最大約1,000 ftだが、通常はより浅い（約100 ft程度）とされる。',
     'sources': [{'title': 'NOAA Fisheries: Short-Beaked Common Dolphin',
                  'url': 'https://www.fisheries.noaa.gov/species/short-beaked-common-dolphin'}]},

    {'id': 'grampus_griseus',
     'jp': 'ハナゴンドウ',
     'en': "Risso's dolphin",
     'sci': 'Grampus griseus',
     'family': 'マイルカ科（Delphinidae）',
     'length': '約2.6–4.0 m（8.5–13 ft）',
     'weight': '約299–499 kg（660–1,100 lb）',
     'lifespan': '少なくとも35年',
     'distribution': '世界の温帯～熱帯の海域に広く分布する。\n'
                     '一般に大陸棚縁辺・大陸斜面の外洋性深海域を好み、少なくとも水深1,000 ftまで潜水し、息止めは30分に達することがある。\n'
                     '緯度64°N〜46°Sの範囲で報告があり、北半球では日本・ロシア・アラスカ湾などを含む。',
     'ecology': '通常10〜30頭の群れで見られるが、単独・ペア、また数百〜数千頭の疎な集合も報告されている。\n他種（例：ハンドウイルカ、コククジラ、キタセミクジライルカ、カマイルカ）と同所的に見られることがある。',
     'sources': [{'title': "NOAA Fisheries: Risso's Dolphin",
                  'url': 'https://www.fisheries.noaa.gov/species/rissos-dolphin'}]},

    {'id': 'pseudorca_crassidens',
     'jp': 'ニセシャチ',
     'en': 'False killer whale',
     'sci': 'Pseudorca crassidens',
     'family': 'マイルカ科（Delphinidae）',
     'length': '約4.9 m（雌 16 ft）/ 約6.1 m（雄 20 ft）',
     'weight': '約1361 kg（3,000 lb）',
     'lifespan': '最大：雌63年／雄58年',
     'distribution': '一般に外洋性の熱帯～亜熱帯で、水深3,300 ft超の深海域を好む。\n一方、ハワイ周辺の個体群では島に近い海域により強く関連する（島嶼の海洋環境が餌生物を集める可能性がある）。',
     'ecology': '社会性が強く、強固な社会的結びつきをもつ。\n'
                '少数個体のサブグループが、数十kmに広がる大きな集合の一部として行動することがあり、採餌の探索に役立つとされる。\n'
                '獲物を捕らえると複数個体が集まり、獲物を分け合う行動が報告されている。ハワイでは40〜50頭規模の集合が見られることがある。',
     'sources': [{'title': 'NOAA Fisheries: False Killer Whale',
                  'url': 'https://www.fisheries.noaa.gov/species/false-killer-whale'}]},

    {'id': 'globicephala_macrorhynchus',
     'jp': 'ゴンドウクジラ（短ヒレ）',
     'en': 'Short-finned pilot whale',
     'sci': 'Globicephala macrorhynchus',
     'family': 'マイルカ科（Delphinidae）',
     'length': '約3.7–7.3 m（12–24 ft）',
     'weight': '約998–2994 kg（2,200–6,600 lb）',
     'lifespan': '35–60年',
     'distribution': '熱帯～温帯の比較的温暖な海域を好み、沖合から沿岸近くまで見られるが、一般に深い海域を好む。\nイカ類の高密度域が主要な採餌場所になる。',
     'ecology': '主にイカ類を食べるが、タコ類や魚類も捕食する。採餌は水深1,000 ft以上の中深層で行われることがある。\n'
                '25〜50頭ほどの群れで見られることが多く、移動・採餌時には群れが横幅0.5マイル程度に広がることがある。\n'
                '深く高速に潜って大型のイカを追うことがあり、深海の高速潜水者として知られる。',
     'sources': [{'title': 'NOAA Fisheries: Short-Finned Pilot Whale',
                  'url': 'https://www.fisheries.noaa.gov/species/short-finned-pilot-whale'}]},

    {'id': 'stenella_coeruleoalba',
     'jp': 'スジイルカ',
     'en': 'Striped dolphin',
     'sci': 'Stenella coeruleoalba',
     'family': 'マイルカ科（Delphinidae）',
     'length': '約2.4 m（雌 8 ft）/ 約2.7 m（雄 9 ft）',
     'weight': '約150 kg（雌 330 lb）/ 約159 kg（雄 350 lb）',
     'lifespan': '最大58年',
     'distribution': '熱帯～暖温帯（約52–84°F）の外洋性で深い海域を好み、大陸棚の沖合（海側）に多い。\n'
                     '北緯50度～南緯40度の範囲で報告が多く、湧昇域や収束帯と関連することがある。\n'
                     '世界的に分布し、日本周辺でも報告がある。',
     'ecology': '通常25〜100頭程度のまとまりのある群れで見られるが、数百〜数千頭の大群になることもある。\n群れ内には年齢・性・繁殖状態などに基づく複雑な個体関係があるとされ、他種の鯨類や海鳥と一緒に見られることは少ない。',
     'sources': [{'title': 'NOAA Fisheries: Striped Dolphin',
                  'url': 'https://www.fisheries.noaa.gov/species/striped-dolphin'}]},

    {'id': 'balaena_mysticetus',
     'jp': 'ホッキョククジラ',
     'en': 'Bowhead whale',
     'sci': 'Balaena mysticetus',
     'family': 'セミクジラ科（Balaenidae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Bowhead Whale', 'url': 'https://www.fisheries.noaa.gov/species/bowhead-whale'}]},

    {'id': 'balaenoptera_borealis',
     'jp': 'イワシクジラ',
     'en': 'Sei whale',
     'sci': 'Balaenoptera borealis',
     'family': 'ナガスクジラ科（Balaenopteridae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Sei Whale', 'url': 'https://www.fisheries.noaa.gov/species/sei-whale'}]},

    {'id': 'eschrichtius_robustus',
     'jp': 'コククジラ',
     'en': 'Gray whale',
     'sci': 'Eschrichtius robustus',
     'family': 'コククジラ科（Eschrichtiidae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Gray Whale', 'url': 'https://www.fisheries.noaa.gov/species/gray-whale'}]},

    {'id': 'balaenoptera_edeni',
     'jp': 'ニタリクジラ',
     'en': "Bryde's whale",
     'sci': 'Balaenoptera edeni',
     'family': 'ナガスクジラ科（Balaenopteridae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': "NOAA Fisheries: Bryde's Whale", 'url': 'https://www.fisheries.noaa.gov/species/brydes-whale'}]},

    {'id': 'kogia_breviceps',
     'jp': 'コハクジラ',
     'en': 'Pygmy sperm whale',
     'sci': 'Kogia breviceps',
     'family': 'マッコウクジラ科（Physeteridae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Pygmy Sperm Whale',
                  'url': 'https://www.fisheries.noaa.gov/species/pygmy-sperm-whale'}]},

    {'id': 'kogia_sima',
     'jp': 'コマッコウ',
     'en': 'Dwarf sperm whale',
     'sci': 'Kogia sima',
     'family': 'マッコウクジラ科（Physeteridae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Dwarf Sperm Whale',
                  'url': 'https://www.fisheries.noaa.gov/species/dwarf-sperm-whale'}]},

    {'id': 'stenella_attenuata',
     'jp': 'マダライルカ',
     'en': 'Pantropical spotted dolphin',
     'sci': 'Stenella attenuata',
     'family': 'マイルカ科（Delphinidae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Pantropical Spotted Dolphin',
                  'url': 'https://www.fisheries.noaa.gov/species/pantropical-spotted-dolphin'}]},

    {'id': 'phocoena_sinus',
     'jp': 'バキータ',
     'en': 'Vaquita',
     'sci': 'Phocoena sinus',
     'family': 'ネズミイルカ科（Phocoenidae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Vaquita', 'url': 'https://www.fisheries.noaa.gov/species/vaquita'}]},

    {'id': 'berardius_bairdii',
     'jp': 'ツチクジラ（ベアードオウギハクジラ）',
     'en': "Baird's beaked whale",
     'sci': 'Berardius bairdii',
     'family': 'アカボウクジラ科（Ziphiidae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': "NOAA Fisheries: Baird's Beaked Whale",
                  'url': 'https://www.fisheries.noaa.gov/species/bairds-beaked-whale'}]},

    {'id': 'ziphius_cavirostris',
     'jp': 'アカボウクジラ',
     'en': "Cuvier's beaked whale",
     'sci': 'Ziphius cavirostris',
     'family': 'アカボウクジラ科（Ziphiidae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': "NOAA Fisheries: Cuvier's Beaked Whale",
                  'url': 'https://www.fisheries.noaa.gov/species/cuviers-beaked-whale'}]},

    {'id': 'globicephala_melas',
     'jp': 'ゴンドウクジラ（長ヒレ）',
     'en': 'Long-finned pilot whale',
     'sci': 'Globicephala melas',
     'family': 'マイルカ科（Delphinidae）',
     'length': '（準備中）',
     'weight': '（準備中）',
     'lifespan': '（準備中）',
     'distribution': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'ecology': '（準備中：NOAA Fisheriesの種ページを根拠に追記予定）',
     'sources': [{'title': 'NOAA Fisheries: Long-Finned Pilot Whale',
                  'url': 'https://www.fisheries.noaa.gov/species/long-finned-pilot-whale'}]}
]

SPECIES_BY_ID = {s["id"]: s for s in SPECIES}

# ---- データ保存先（data/ に保存：サーバ再起動後も保持） ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

VISITOR_FILE = os.path.join(DATA_DIR, 'visitor_count.json')
SEARCH_FILE = os.path.join(DATA_DIR, 'search_counts.json')
BBS_FILE = os.path.join(DATA_DIR, 'bbs_messages.csv')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')


def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_bbs_messages():
    if not os.path.exists(BBS_FILE):
        return []
    try:
        with open(BBS_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            out = []
            for row in reader:
                out.append({
                    'ts': row.get('ts', ''),
                    'user': row.get('user', ''),
                    'text': row.get('text', ''),
                })
            return out
    except Exception:
        return []


def append_bbs_message(msg):
    file_exists = os.path.exists(BBS_FILE)
    with open(BBS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['ts', 'user', 'text'])
        if not file_exists:
            writer.writeheader()
        writer.writerow(msg)


# ---- カウンタ等（data/ から読み込み） ----
VISITOR_COUNT = int(load_json(VISITOR_FILE, {}).get('count', 0) or 0)

_search_data = load_json(SEARCH_FILE, {})
CURRENT_WEEK_ID = _search_data.get('week_id')
SEARCH_COUNTS = _search_data.get('counts', {}) if isinstance(_search_data.get('counts', {}), dict) else {}
SEARCH_COUNTS = {k: int(v) for k, v in SEARCH_COUNTS.items() if isinstance(k, str)}

BBS_MESSAGES = load_bbs_messages()  # {'user': '...', 'text': '...', 'ts': '...'}

USERS = load_json(USERS_FILE, {})
if not isinstance(USERS, dict):
    USERS = {}


def week_id_today():
    # ISO週番号（年-週）
    today = datetime.date.today()
    iso = today.isocalendar()  # (year, week, weekday)
    return f"{iso[0]}-W{iso[1]:02d}"


def save_visitor_count():
    save_json(VISITOR_FILE, {'count': VISITOR_COUNT})


def save_search_counts():
    save_json(SEARCH_FILE, {'week_id': CURRENT_WEEK_ID, 'counts': SEARCH_COUNTS})


def reset_weekly_counts_if_needed():
    global CURRENT_WEEK_ID, SEARCH_COUNTS
    wid = week_id_today()
    if CURRENT_WEEK_ID != wid:
        CURRENT_WEEK_ID = wid
        SEARCH_COUNTS = {}
        save_search_counts()


def touch_visit():
    """同一ブラウザ（セッション）を1訪問として数える簡易実装"""
    global VISITOR_COUNT
    if not session.get('counted_visit', False):
        VISITOR_COUNT += 1
        session['counted_visit'] = True
        save_visitor_count()


def is_logged_in():
    return bool(session.get("logged_in", False))


def current_user():
    return session.get("user", "")


def get_user_record(username):
    rec = USERS.get(username)
    return rec if isinstance(rec, dict) else None


def save_users():
    save_json(USERS_FILE, USERS)


def normalize_favorites(favs):
    if not isinstance(favs, list):
        favs = []
    seen = set()
    out = []
    for x in favs:
        if isinstance(x, str) and x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def user_favorites(username):
    rec = get_user_record(username)
    if not rec:
        return []
    favs = normalize_favorites(rec.get("favorites", []))
    if favs != rec.get("favorites", []):
        rec["favorites"] = favs
        USERS[username] = rec
        save_users()
    return favs


def set_user_favorites(username, favs):
    rec = get_user_record(username)
    if not rec:
        return
    rec["favorites"] = normalize_favorites(favs)
    USERS[username] = rec
    save_users()


def validate_username(username):
    # ユーザー名は 3〜20 文字、英数字とアンダースコアのみ
    if username is None:
        return False, "ユーザー名を入力してください。"
    username = username.strip()
    if len(username) < 3 or len(username) > 20:
        return False, "ユーザー名は3〜20文字で入力してください。"
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    for c in username:
        if c not in allowed:
            return False, "ユーザー名は英数字とアンダースコア（_）のみ使用できます。"
    return True, ""


def common_context():
    favs = user_favorites(current_user()) if is_logged_in() else []
    return {
        "login_user": current_user(),
        "logged_in": is_logged_in(),
        "visitor_count": VISITOR_COUNT,
        "total_species": len(SPECIES),
        "favorites_count": len(favs),
        "week_id": CURRENT_WEEK_ID or week_id_today(),
    }


def pick_today_species():
    # 日付から決定的に1種を選ぶ（サーバ再起動に依存しない）
    idx = datetime.date.today().toordinal() % len(SPECIES)
    return SPECIES[idx]


def top_week_species(limit=3):
    # 週の検索回数上位（同数なら種名で安定ソート）
    items = [(sid, cnt) for sid, cnt in SEARCH_COUNTS.items() if sid in SPECIES_BY_ID]
    items.sort(key=lambda t: (-t[1], SPECIES_BY_ID[t[0]]["jp"]))
    top = []
    for sid, cnt in items[:limit]:
        s = dict(SPECIES_BY_ID[sid])
        s["count"] = cnt
        top.append(s)
    return top


@app.route("/login", methods=["GET", "POST"])
def login():
    touch_visit()
    reset_weekly_counts_if_needed()

    # 既にログイン済みならマイページへ
    if is_logged_in():
        return redirect(url_for("mypage"))



    message = ""
    if request.method == "POST":
        username = (request.form.get("username", "") or "").strip()
        pw = request.form.get("password", "") or ""


        session["user_prefill"] = username

        rec = get_user_record(username)
        pw_hash = (rec or {}).get("pw_hash", "")
        if rec and pw_hash and check_password_hash(pw_hash, pw):
            session["user"] = username
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            message = "ユーザー名またはパスワードが違います。"

    user_prefill = session.get("user_prefill", "")
    return render_template(
        "login.html",
        user_prefill=user_prefill,
        message=message,
        **common_context(),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    touch_visit()
    reset_weekly_counts_if_needed()

    if is_logged_in():
        return redirect(url_for("mypage"))

    message = ""
    if request.method == "POST":
        username = (request.form.get("username", "") or "").strip()
        pw = request.form.get("password", "") or ""
        pw2 = request.form.get("password2", "") or ""

        session["user_prefill"] = username

        ok, msg = validate_username(username)
        if not ok:
            message = msg
        elif username in USERS:
            message = "そのユーザー名は既に使用されています。別のユーザー名にしてください。"
        elif len(pw) < 4:
            message = "パスワードは4文字以上で設定してください。"
        elif pw != pw2:
            message = "パスワード（確認）が一致しません。"
        else:
            USERS[username] = {
                "pw_hash": generate_password_hash(pw),
                "created_at": datetime.date.today().strftime("%Y-%m-%d"),
                "favorites": [],
            }
            save_users()
            return redirect(url_for("login"))

    user_prefill = session.get("user_prefill", "")
    return render_template(
        "register.html",
        user_prefill=user_prefill,
        message=message,
        **common_context(),
    )


@app.route("/mypage")
def mypage():
    touch_visit()
    reset_weekly_counts_if_needed()
    if not is_logged_in():
        return redirect(url_for("login"))

    username = current_user()
    rec = get_user_record(username) or {}
    favs = user_favorites(username)

    return render_template(
        "mypage.html",
        username=username,
        created_at=rec.get("created_at", ""),
        favorites_count_user=len(favs),
        **common_context(),
    )


@app.route("/logout")
def logout():
    touch_visit()
    reset_weekly_counts_if_needed()

    counted = bool(session.get("counted_visit", False))
    session.clear()
    # 訪問者数の多重加算を避けるため、訪問カウントのフラグは保持
    session["counted_visit"] = counted

    return redirect(url_for("home"))


@app.route("/")
def home():
    touch_visit()
    reset_weekly_counts_if_needed()

    today = pick_today_species()
    top = top_week_species(limit=5)

    return render_template(
        "home.html",
        today_species=today,
        top_week=top,
        **common_context(),
    )


@app.route("/search")
def search():
    touch_visit()
    reset_weekly_counts_if_needed()

    q = request.args.get("q", "").strip()
    results = []
    if q:
        q_lower = q.lower()
        for s in SPECIES:
            hay = f'{s["jp"]} {s["en"]} {s["sci"]}'.lower()
            if q_lower in hay:
                results.append(s)

    return render_template(
        "search_results.html",
        q=q,
        results=results,
        **common_context(),
    )


@app.route("/species/<species_id>")
def species_detail(species_id):
    touch_visit()
    reset_weekly_counts_if_needed()

    s = SPECIES_BY_ID.get(species_id)
    if s is None:
        return render_template("not_found.html", **common_context()), 404

    # 検索結果から遷移した場合のみカウント（今週の検索回数）
    if request.args.get("from", "") == "search":
        SEARCH_COUNTS[species_id] = SEARCH_COUNTS.get(species_id, 0) + 1
        save_search_counts()

    favs = user_favorites(current_user()) if is_logged_in() else []
    is_fav = species_id in favs

    return render_template(
        "species_detail.html",
        sp=s,
        is_fav=is_fav,
        **common_context(),
    )


@app.route("/favorite/<species_id>", methods=["POST"])
def favorite_add(species_id):
    touch_visit()
    reset_weekly_counts_if_needed()
    if not is_logged_in():
        return redirect(url_for("login"))

    if species_id in SPECIES_BY_ID:
        username = current_user()
        favs = user_favorites(username)
        if species_id not in favs:
            favs.append(species_id)
            set_user_favorites(username, favs)

    return redirect(url_for("species_detail", species_id=species_id))


@app.route("/favorite_remove/<species_id>", methods=["POST"])
def favorite_remove(species_id):
    touch_visit()
    reset_weekly_counts_if_needed()
    if not is_logged_in():
        return redirect(url_for("login"))

    username = current_user()
    favs = user_favorites(username)
    favs = [x for x in favs if x != species_id]
    set_user_favorites(username, favs)

    return redirect(url_for("favorites"))


@app.route("/favorites")
def favorites():
    touch_visit()
    reset_weekly_counts_if_needed()

    favs = user_favorites(current_user()) if is_logged_in() else []
    fav_species = [SPECIES_BY_ID[sid] for sid in favs if sid in SPECIES_BY_ID]

    return render_template(
        "favorites.html",
        fav_species=fav_species,
        **common_context(),
    )


@app.route("/bbs", methods=["GET", "POST"])
def bbs():
    touch_visit()
    reset_weekly_counts_if_needed()

    if request.method == "POST":
        if not is_logged_in():
            return redirect(url_for("login"))

        text = request.form.get("message", "").strip()
        if text:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            BBS_MESSAGES.append({"user": current_user(), "text": text, "ts": ts})
            append_bbs_message({"ts": ts, "user": current_user(), "text": text})
        # POST後はredirect（リロード多重投稿を防ぐ）
        return redirect(url_for("bbs"))

    # 最新が上になるよう表示
    msgs = list(reversed(BBS_MESSAGES[-50:]))
    return render_template(
        "bbs.html",
        messages=msgs,
        **common_context(),
    )


@app.route('/stats')
def stats():
    """サイト内の簡易統計（加点要素：追加ルート + 2変数以上渡し）"""
    touch_visit()
    reset_weekly_counts_if_needed()

    top10 = top_week_species(limit=10)
    total_searches = sum(SEARCH_COUNTS.values())
    bbs_total = len(BBS_MESSAGES)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    chart_available = (plt is not None)

    return render_template(
        'stats.html',
        top10=top10,
        total_searches=total_searches,
        bbs_total=bbs_total,
        now_str=now_str,
        chart_available=chart_available,
        **common_context(),
    )


@app.route('/stats/search_chart.png')
def stats_search_chart():
    """今週の検索回数トップをグラフPNGで返す（matplotlib が無い場合は 404）"""
    if plt is None:
        abort(404)

    top10 = top_week_species(limit=10)
    if not top10:
        abort(404)

    labels = [s['jp'] for s in top10]
    values = [s.get('count', 0) for s in top10]

    fig = plt.figure(figsize=(9, 4.5))
    ax = fig.add_subplot(111)
    ax.bar(range(len(values)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel('回')
    ax.set_title('今週の検索回数トップ（上位10）')
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')
@app.route("/data")
def data():
    """収録リスト（確認用）"""
    touch_visit()
    reset_weekly_counts_if_needed()
    return render_template("data.html", species=SPECIES, **common_context())


if __name__ == "__main__":
    app.run(debug=True)
