# -*- coding: utf-8 -*-
"""NIKKE 官方背景图管理与角色关联映射。

支持：
1. 扫描 resources/background/ 下的 330+ 张官方解包场景图；
2. 为背景建立中文显示名、分类分组（皇冠王国、方舟核心、前哨基地设施、自然风光/荒原、特别活动等）；
3. 根据当前角色（英文名、中文名、部队/据点）提供推荐背景。

自定义背景（扩图工作流）：
- resources/output/  导出目录：导出当前所选背景到此，外部工具（PS / SD 扩图）处理后，
                     成品放进 resources/input/；
- resources/input/   导入目录：软件「导入扩图」扫描这里，把成品收进自定义背景库；
- resources/custom/  自定义背景库：导入回来的成果持久保存，与官方背景一同参与
                     预览、超分、动态壁纸导出。
- 同名时自定义优先（用户导入的版本覆盖官方同名图，可在前端删除自定义以还原）。
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Any, NamedTuple
from PIL import Image

# 资源目录名（相对 resources/）
BACKGROUND_DIRNAME = "background"
CUSTOM_DIRNAME = "custom"
OUTPUT_DIRNAME = "output"
INPUT_DIRNAME = "input"
PREVIEW_DIRNAME = "preview"

# 可作为背景导入/导出的图片扩展名（扩图工具可能输出 jpg/webp）
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
# 参与超分与壁纸导出的扩展名（超分引擎只吃 png，其余格式导入时统一转 png）
UPSCALABLE_EXTS = {".png"}
# 自定义背景缩略图后缀：与官方同名背景区分，互不覆盖
CUSTOM_THUMB_SUFFIX = "__custom"


class BackgroundDirs(NamedTuple):
    """背景相关目录集合。

    用具名字段而非裸元组：此前 3/4 元组按位置解包错位过一次（outpaint 被当成 preview，
    导致超分产物永远解析不到），改成 NamedTuple 后只按名字访问，不会再错位。
    """

    official: Path
    custom: Path
    output: Path
    input: Path
    preview: Path


def background_dirs(root: Path) -> BackgroundDirs:
    """返回背景相关目录集合（official / custom / output / input / preview）。"""
    res = Path(root) / "resources"
    return BackgroundDirs(
        official=res / BACKGROUND_DIRNAME,
        custom=res / CUSTOM_DIRNAME,
        output=res / OUTPUT_DIRNAME,
        input=res / INPUT_DIRNAME,
        preview=res / PREVIEW_DIRNAME,
    )


# 分类定义与背景文件名前缀/模式匹配
CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "custom",
        "name": "自定义 / 扩图",
        "keywords": [],
    },
    {
        "id": "crown_kingdom",
        "name": "皇冠王国",
        "keywords": ["crowncastle", "crowncaslte", "crownkingdom"],
    },
    {
        "id": "the_ark",
        "name": "方舟都会与设施",
        "keywords": [
            "ark", "briefingroom", "commanderroom", "corridor", "elevator",
            "enikkroom", "missilisoffice", "nikkecorridor", "nikkeroom",
            "office", "goodoffice", "whitehouse", "police", "jail",
            "laboratory", "simulationroom", "techindoor", "buildinglobby",
            "royalroad", "fastfood", "fastfood", "shoppingmall", "shoppingstreet",
            "clothingstore", "toyshop", "library", "theater", "gym",
            "dancepracticeroom", "hospital", "station", "azxin", "metro",
        ],
    },
    {
        "id": "outpost",
        "name": "前哨基地",
        "keywords": [
            "outpost", "armory", "workshop", "machineroom", "giantparticlecannon",
            "harmonycube", "bar", "piratepub", "cafe", "maidcafe",
            "mafiaoffice", "temporarycamp", "trainingfield", "park",
            "flowergarden", "flowerroad", "airview", "apillar",
            "goddessofvictory", "wingofvictory", "square",
        ],
    },
    {
        "id": "eden",
        "name": "伊甸园",
        "keywords": ["eden", "secretgarden"],
    },
    {
        "id": "resort_beach",
        "name": "海滩与度假村",
        "keywords": [
            "beach", "bluewaterisland", "cleanbeach", "coralisland", "pinkbeach",
            "redbeach", "redocean", "cruiseshippool", "deck", "deepwater",
            "krakenrockisland", "pilothouse", "pool", "silentbeach",
            "uninhabitedisland", "voyage", "waterfall", "ocean",
        ],
    },
    {
        "id": "hotspring",
        "name": "雪原与温泉",
        "keywords": [
            "hotspring", "bighotspring", "iceland", "snowtown", "winter", "loghouse",
        ],
    },
    {
        "id": "coin_rush",
        "name": "金币狂潮 / 赌场",
        "keywords": ["coinrush", "amusementpark", "stage"],
    },
    {
        "id": "crystal_oldtales",
        "name": "水晶地带 / 童话故事",
        "keywords": [
            "crystal", "brokencrystal", "cinderellasky", "e2crystal",
            "manycrystal", "neongrave",
        ],
    },
    {
        "id": "wasteland_surface",
        "name": "地面荒原与废墟",
        "keywords": [
            "wasteland", "desert", "destroyedcity", "destroyedstreet", "ruin",
            "burningcity", "cityforest", "city", "bambooforest", "jungle",
            "bog", "silverbog", "silversea", "blacksea", "blackwaterfall",
            "blackpuddle", "volcano", "greathole", "junkmountain",
            "outerrim", "outertomb", "tomb", "lostsector", "sealroom",
            "spaceelevator", "skyelevator", "dragoncaslte", "dragoncastle",
            "atlascage", "artcity", "bubblemaker", "drain", "factory",
            "freezer", "gatekeeper", "havester", "kitchen", "lake",
            "launcher", "livingroom", "massiveobject", "memorialhall",
            "nocloudland", "restarea", "restaurant", "school", "showerroom",
            "sky", "storage", "sunset", "tatamiroom", "trail", "treeofwater",
            "silentcave", "talkative", "wunder",
        ],
    },
]

# 角色 -> 专属/推荐背景映射 (使用小写匹配)
CHARACTER_RECOMMENDED_BACKGROUNDS: dict[str, list[str]] = {
    # 白骑士
    "crown": ["CrownCastleFrontYard_d.png", "CrownCastleGate_d.png", "CrownCastleDiningRoom_d.png", "Crowncastlebedroom_d.png", "CrownCasltePanorama_s.png"],
    "chime": ["CrownCastleFrontYard_d.png", "CrownCastleGate_d.png", "CrownCastleDiningRoom_d.png"],
    "kilo": ["CrownCastleGate_d.png", "CrownCastleFrontYard_d.png"],
    "modernia": ["CrownCastleFrontYard_d.png", "CommanderRoom.png", "CinderellaSky_1.png", "Sky.png"],

    # 反击部队 / 指挥官
    "rapi": ["CommanderRoom.png", "Ark.png", "BriefingRoom.png", "TrainingField.png", "WasteLand_01.png"],
    "anis": ["CommanderRoom.png", "OutpostOut.png", "PinkBeachIsland_d.png", "Pool.png", "Bar.png"],
    "neon": ["CommanderRoom.png", "Armory.png", "NeonGrave.png", "CleanBeach.png"],
    "marian": ["CommanderRoom.png", "BriefingRoom.png", "FlowerGarden.png"],

    # 伊甸园 / 寻宝者
    "dorothy": ["Eden.png", "EdenIndoor.png", "SecretGarden.png", "GoddessOfVictory.png", "Paradise"],
    "noah": ["Eden.png", "EdenLobby.png"],
    "harran": ["Eden.png", "SecretGarden.png", "Forest"],
    "isabel": ["Eden.png", "EdenIndoor.png"],
    "red hood": ["Desert_01.png", "Wasteland_01.png", "Sunset.png", "Bar.png"],
    "snow white": ["IceLand_01.png", "WasteLand_01.png", "GoddessOfVictory.png"],
    "scarlet": ["BambooForest_d.png", "BambooForest_s.png", "CherryBlossom.png", "GoddessOfVictory.png"],
    "rapunzel": ["Church.png", "GoddessOfVictory.png", "FlowerGarden.png"],

    # 童话 / 二代
    "cinderella": ["CinderellaSky_1.png", "CrystalCity.png", "CrystalField_1.png", "BrokenCrystal_1.png"],
    "grave": ["NeonGrave.png", "CrystalDesert_d.png", "WasteLand_01.png"],

    # 女仆咖啡厅
    "cocoa": ["MaidCafe.png", "Cafe.png", "Cafe_n.png"],
    "soda": ["MaidCafe.png", "Cafe.png", "CoinRushIndoor.png"],
    "ade": ["MaidCafe.png", "Cafe.png", "CoinRushIndoor.png"],
    "privaty": ["WhiteHouse.png", "MaidCafe.png", "Office.png"],

    # 777 赌场
    "blanc": ["CoinRushMainHall.png", "CoinRushGameZone.png", "CoinRushDrinkZone.png", "Stage.png"],
    "noir": ["CoinRushMainHall.png", "CoinRushGameZone.png", "CoinRushDrinkZone.png", "Stage.png"],
    "rouge": ["CoinRushMainHall.png", "CoinRushGameZone.png"],

    # 极乐净土 / 警局
    "poli": ["Police.png", "Office.png"],
    "miranda": ["Police.png", "Office.png"],
    "quiry": ["Police.png"],

    # 列车
    "diesel": ["Station.png", "Station_n.png", "AZXIn.png"],
    "brid": ["Station.png", "Station_n.png", "AZXIn.png"],
    "soline": ["Station.png", "Station_n.png", "AZXIn.png"],

    # 工坊
    "liter": ["Workshop.png", "MachineRoom.png"],
    "centi": ["Workshop.png", "MachineRoom.png"],

    # 军械
    "emma": ["Armory.png", "BriefingRoom.png"],
    "eunhwa": ["Armory.png", "BriefingRoom.png"],
    "vesti": ["Armory.png", "SchoolCommandCenter_d.png"],

    # 医疗
    "mary": ["Hospital.png", "Hospital_n.png", "CleanBeach.png", "PinkBeachIsland_d.png"],
    "pepper": ["Hospital.png", "Hospital_n.png", "CleanBeach.png"],

    # 商业 / 娱乐
    "rupee": ["ShoppingMall.png", "ShoppingStreet_d.png", "Winter_AmusementPark.png", "HotSpring.png"],
    "yan": ["ShoppingMall.png", "ShoppingStreet_d.png"],
    "dolla": ["ShoppingMall.png", "Mafiaoffice.png", "Bar.png"],

    # 温泉活动
    "ludmilla": ["HotSpringInnIn_d.png", "HotSpringInnOut_d.png", "BigHotSpring_d.png", "IceLand_01.png"],
    "tove": ["IceLand_01.png", "IceLand_02.png", "SnowTown_d.png"],
    "neve": ["IceLand_01.png", "IceLand_02.png"],
    "alice": ["ClothingStore.png", "AmusementPark.png", "IceLand_01.png"],

    # 咖啡厅 / 甜点
    "sugar": ["Cafe.png", "Cafe_n.png", "Bar.png"],
    "frima": ["Cafe.png", "Cafe_n.png"],
    "milk": ["Cafe.png", "Cafe_n.png", "Gym.png"],

    # 音乐
    "volume": ["Stage.png", "Theater.png"],
    "noise": ["Stage.png", "Theater.png"],
    "aria": ["Theater.png", "Stage.png"],
    "julia": ["Theater.png", "Stage.png"],

    # 尼尔联动
    "2b": ["DestroyedStreet.png", "Destroyedcity.png", "Factory.png"],
    "a2": ["DestroyedStreet.png", "Destroyedcity.png", "Factory.png"],
    "9s": ["DestroyedStreet.png", "Destroyedcity.png", "Factory.png"],

    # EVA 联动
    "asuka": ["SchoolCommandCenter_d.png", "SchoolCorridor.png", "Cockpit_E_1.png"],
    "rei": ["SchoolCommandCenter_d.png", "SchoolCorridor.png", "Cockpit_E_2.png"],
    "mari": ["SchoolCommandCenter_d.png", "SchoolCorridor.png", "Cockpit_E_1.png"],
}

# 中文角色名简称映射 -> 英文键
CN_TO_EN_KEY: dict[str, str] = {
    "皇冠": "crown",
    "钟鸣": "chime",
    "吉洛": "kilo",
    "神罚": "modernia",
    "拉毗": "rapi",
    "阿尼斯": "anis",
    "尼恩": "neon",
    "玛丽安": "marian",
    "桃乐丝": "dorothy",
    "诺雅": "noah",
    "哈兰": "harran",
    "伊莎贝尔": "isabel",
    "小红帽": "red hood",
    "白雪公主": "snow white",
    "红莲": "scarlet",
    "长发公主": "rapunzel",
    "灰姑娘": "cinderella",
    "格拉维": "grave",
    "可可": "cocoa",
    "索达": "soda",
    "艾德": "ade",
    "普琳玛": "privaty",
    "普丽瓦蒂": "privaty",
    "白兔": "blanc",
    "布兰儿": "blanc",
    "黑兔": "noir",
    "诺亚尔": "noir",
    "红兔": "rouge",
    "波莉": "poli",
    "米兰达": "miranda",
    "奎琳": "quiry",
    "迪赛尔": "diesel",
    "布丽德": "brid",
    "索林": "soline",
    "丽塔": "liter",
    "琴": "centi",
    "艾玛": "emma",
    "银华": "eunhwa",
    "贝斯蒂": "vesti",
    "玛丽": "mary",
    "佩珀": "pepper",
    "露菲": "rupee",
    "燕": "yan",
    "朵拉": "dolla",
    "鲁德米拉": "ludmilla",
    "托薇": "tove",
    "尼芙": "neve",
    "爱丽丝": "alice",
    "舒格": "sugar",
    "普利姆": "frima",
    "米尔克": "milk",
    "沃伦姆": "volume",
    "诺伊斯": "noise",
    "阿丽亚": "aria",
    "尤利娅": "julia",
}


def _clean_str(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# 官方剧情场景中英文精准对照字典（支持模糊前缀匹配）
SCENE_CHINESE_NAMES: dict[str, str] = {
    # 核心据点与方舟都会
    "Ark": "方舟都会",
    "ArkCleanIndoor": "方舟 · 洁净室内",
    "ArkRuinIndoor": "方舟 · 遗迹废墟",
    "Ark_02": "方舟都会 · 街区",
    "BriefingRoom": "前哨司令部 · 简报室",
    "CommanderRoom": "指挥官办公室",
    "NikkeRoom": "妮姬生活宿舍",
    "NikkeCorridor": "妮姬生活区走廊",
    "EnikkRoom": "艾尼克中枢主脑室",
    "MissilisOffice": "米西利斯总裁办公室",
    "Office": "方舟高层办公厅",
    "GoodOffice": "高级行政办公室",
    "Corridor": "通行长廊",
    "Elevator": "核心升降电梯",
    "ElevatorOut": "升降电梯出入口",
    "BuildingLobby": "摩天大楼迎宾大厅",
    "RoyalRoad": "方舟中央皇家大道",
    "OuterRim": "方舟外环贫民窟",
    "OuterrimWall": "外环隔离重防壁",
    "OuterTomb": "外环残破冢墓",
    "Jail": "重犯禁闭监狱",
    "JailCorridor": "监狱戒备长廊",
    "Laboratory": "绝密科技研究所",
    "SimulationRoom": "战术模拟训练室",
    "TechIndoor": "高新科技实验室",

    # 皇冠王国 & 伊甸园
    "CrownCastleFrontYard": "皇冠城堡 · 前院",
    "CrownCastleGate": "皇冠城堡 · 正门",
    "CrownCastleDiningRoom": "皇冠城堡 · 宴会厅",
    "Crowncastlebedroom": "皇冠城堡 · 卧室",
    "CrownCasltePanorama": "皇冠城堡 · 远眺全景",
    "DragonCastleIn": "龙之古堡 · 殿堂内景",
    "DragonCaslteOut": "龙之古堡 · 峻险外观",
    "Eden": "伊甸园秘境",
    "EdenIndoor": "伊甸园 · 内部核心",
    "EdenLobby": "伊甸园 · 迎宾大堂",
    "SecretGarden": "伊甸园 · 秘密花园",

    # 娱乐商业与前哨设施
    "CoinRushMainHall": "金币狂潮 · 豪华大厅",
    "CoinRushGameZone": "金币狂潮 · 娱乐游艺区",
    "CoinRushDrinkZone": "金币狂潮 · 奢华吧台",
    "CoinRushIndoor": "金币狂潮 · 贵宾休闲区",
    "Stage": "璀璨演艺舞台",
    "Theater": "皇家艺术大剧院",
    "Station": "前哨火车站",
    "AZXIn": "AZX无限列车 · 豪华车厢",
    "Armory": "前哨反击军械库",
    "Workshop": "丽塔工坊",
    "MachineRoom": "核心动力机械机房",
    "Hospital": "前哨战地医院",
    "MaidCafe": "女仆温馨咖啡厅",
    "Cafe": "悠闲咖啡馆",
    "Police": "A.C.P.U.警察局",
    "Gym": "活力健身俱乐部",
    "dancepracticeroom": "偶像舞蹈练习室",
    "WhiteHouse": "方舟审判法庭",
    "Church": "寂静祈愿教堂",
    "ClothingStore": "时髦服装精品店",
    "ToyShop": "趣味机械玩具屋",
    "Library": "方舟大图书馆",
    "FastFood": "快餐厅",
    "Restaurant": "浪漫西餐厅",
    "DiningRoom": "典雅餐厅",
    "Hotel": "奢华度假酒店",
    "Lobby": "酒店前堂",
    "LivingRoom": "温馨生活客厅",
    "Kitchen": "料理厨房",
    "ShowerRoom": "浴室淋浴间",
    "TatamiRoom": "传统和风榻榻米",
    "Storage": "后勤物资储备库",

    # 前哨地表与标志建筑
    "OutpostOut": "前哨基地 · 地表入口",
    "TrainingField": "前哨战术训练场",
    "TemporaryCamp": "地表探索临时营地",
    "RestArea": "荒野行军休息站",
    "FlowerGarden": "花语烂漫花园",
    "FlowerRoad": "繁花漫步道",
    "Park": "前哨休闲公园",
    "AmusementPark": "欢乐游乐园",
    "Winter_AmusementPark": "冰雪盛冬游乐园",
    "AirView": "苍穹天文观测台",
    "APillar": "方舟支撑天柱",
    "GoddessOfVictory": "胜利女神纪念雕像",
    "WingOfVictory": "胜利之翼荣耀雕像",
    "Square": "中央广场",
    "HarmonyCube": "和谐方块能量塔",
    "GiantParticleCannon": "巨型轨道粒子加农炮",
    "Bar": "潮流霓虹酒吧",
    "PiratePub": "海盗热带酒馆",
    "Mafiaoffice": "种子俱乐部 · 极道所",
    "MemorialHall": "英灵纪事殿堂",

    # 水晶与第二代
    "CinderellaSky": "灰姑娘的纯澈苍穹",
    "CrystalCity": "远古水晶都城",
    "CrystalField": "纯白水晶平原",
    "CrystalDesert": "无垠水晶大漠",
    "ManyCrystalDesert": "万仞结晶巨漠",
    "BrokenCrystal": "破碎的水晶遗址",
    "Crystalchunk": "水晶结晶巨岩",
    "NeonGrave": "霓虹之墓",
    "E2Crystal": "二代高纯水晶带",

    # 海洋、沙滩与度假温泉
    "Beach": "盛夏阳光海滩",
    "CleanBeach": "洁白无暇沙滩",
    "PinkBeachIsland": "梦幻粉红沙滩岛",
    "NewPinkBeach": "粉红沙滩新景",
    "BluewaterIsland": "蔚蓝盛夏群岛",
    "CoralIsland": "绚烂珊瑚岛",
    "CoralIslandInside": "珊瑚岛溶洞内景",
    "BeachCave": "海蚀岩石洞穴",
    "BeachCaveFog": "薄雾海蚀洞穴",
    "CruiseShipPool": "豪华游轮甲板泳池",
    "Deck": "游轮观景甲板",
    "DeepWater": "深海幽蓝潜流",
    "DeepWater_02": "深海极渊",
    "Pilothouse": "远洋轮船驾驶室",
    "Pool": "度假休闲露天泳池",
    "SilentBeach": "静默海滨海岸",
    "UninhabitedIsland": "原始无人荒岛",
    "Voyage": "远洋航海波澜",
    "WaterFall": "苍翠悬崖飞瀑",
    "ocean": "浩瀚汪洋海景",
    "ocean_bye": "夕阳海平线",
    "ocean_sky": "海天一色",
    "ocean_r": "异色微澜海洋",
    "ocean_r_2": "夜暮之海",
    "RedBeach": "赤红血色海滩",
    "RedOcean": "赤色绯红之海",
    "RedOcean_s": "赤海落日黄昏",
    "RedOcean_s_2": "赤红余晖洋流",
    "RedOcean_s_hole": "赤海大空洞",
    "KrakenRockIsland": "海妖巨岩礁岛",
    "HotSpring": "温泉秘境",
    "BigHotSpring": "露天雪峰大温泉",
    "HotSpringInnIn": "温泉旅馆 · 内庭和室",
    "HotSpringInnOut": "温泉旅馆 · 风雅门庭",
    "LogHouseIn": "雪原木屋 · 暖炉内景",
    "LogHouseOut": "雪原木屋 · 积雪门廊",
    "Lake": "静谧森林湖泊",

    # 废土、荒原与残骸
    "WasteLand": "地表苍凉废土",
    "Desert": "烈日灼烤荒漠",
    "Destroyedcity": "崩毁残破都市",
    "DestroyedStreet": "瓦砾废墟街区",
    "BurningCity": "熊熊战火燃烧之都",
    "City": "地表废弃旧城区",
    "City_d": "日光旧都市",
    "CityForest": "都市丛林废迹",
    "CityForest_001": "都市密林一角",
    "BambooForest": "潇潇静谧竹林",
    "CherryBlossom": "春日樱花漫舞",
    "CountryVillage": "沉寂田园古村",
    "Grassland": "辽阔地表草甸",
    "GreatHole": "巨大深陷天坑",
    "JunkMountain": "机械残骸废铁高山",
    "Factory": "破败古代机械工场",
    "Backstreet": "暗巷后街深处",
    "SpaceElevator": "太空轨道巨构电梯",
    "SkyElevatorIn": "轨道电梯内舱",
    "RuinIndoor": "地表地下遗迹核心",
    "RuinTechIndoor": "遗迹失落科技长廊",
    "LostSector": "迷失禁忌扇区",
    "SealRoom": "重重密封石室",
    "SealRoom_af": "开启后的密封室",
    "Volcano": "熔岩炽热火山",
    "SnowTown": "茫茫覆雪小镇",
    "IceLand": "极寒坚冰雪原",
    "TreeOfWater": "生命泉涌巨树",
    "Bog": "湿冷腐殖泥沼",
    "SilverBog": "银白荧光沼泽",
    "SilverSea": "银光翻涌之海",
    "BlackSea": "漆黑无光暗海",
    "BlackSeaJungle": "暗海腐殖热带雨林",
    "BlackWaterfall": "幽暗黑瀑飞流",
    "BlackPuddle": "黑油泥水滩",
    "Trail": "荒芜地表小径",
    "NoCloudLand": "万里无云旷野",
    "Sky": "晴朗天幕",
    "Sky2": "蔚蓝长空",
    "Sunset": "残阳晚霞落日",
    "Tomb": "荒野英雄古冢",
    "BubbleMaker": "奇趣泡泡生成机",
    "AtlasCage": "阿特拉斯铁锁牢笼",
    "Atlascage": "阿特拉斯巨笼",
    "artcity": "艺术都会遗迹",
    "bunkerofartist": "艺术家的地下堡垒",
    "Drain": "地下排水枢纽",
    "EggArea": "异化生物育卵区",
    "EmptyArea": "空旷荒凉死域",
    "EmptyShelter": "废弃地底庇护所",
    "EzsFull": "能量补给枢纽 · 全负荷",
    "EzsUp": "能量中继站 · 升降机台",
    "Freezer": "超低温冷冻储存库",
    "FreezerIn": "冷冻库内部深处",
    "Freezerout": "冷冻库大门通道",
    "GateKeeper": "门扉看守异端驻地",
    "Havester": "收割者巨像残骸",
    "Jungle1": "繁茂雨林浅滩",
    "Jungle2": "幽暗密林深处",
    "JungleBuilding": "密林废弃设施",
    "Launcher": "轨道加农发射井",
    "Launcher_load": "发射准备就绪态",
    "MassiveObject": "巨大不明异星残骸",
    "talkative_action": "战术对峙演出现场",
    "AAAWunder": "奇迹号巡洋旗舰",
    "Arboretum": "中央生态植物温室",
    "BattleShipBridge": "巨型歼灭舰指挥舰桥",

    # 联动与学院特别活动
    "SchoolCommandCenter": "第一高中 · 战术指挥室",
    "SchoolCorridor": "第一高中 · 明亮长廊",
    "Classroom": "第一高中 · 学院教室",
    "Cockpit_E": "EVA泛用机甲驾驶舱",
    "2025FoolsDay": "2025愚人节特别演出舞台",
    "lbg_lobby_newyear": "新春迎新特别舞台",
    "snbg_sprout": "萌芽生长特别物语",
    "silentcave": "幽寂钟乳石溶洞",
}


def _friendly_name(fn: str) -> str:
    """由文件名生成优雅的官方中文场景标题（附带时段与编号后缀）。"""
    base_name = Path(fn).stem

    # 1. 识别时段后缀
    time_tag = ""
    clean_stem = base_name
    if clean_stem.endswith("_d"):
        time_tag = " (昼)"
        clean_stem = clean_stem[:-2]
    elif clean_stem.endswith("_n"):
        time_tag = " (夜)"
        clean_stem = clean_stem[:-2]
    elif clean_stem.endswith("_s"):
        time_tag = " (夕)"
        clean_stem = clean_stem[:-2]
    elif clean_stem.endswith("_r"):
        time_tag = " (变体)"
        clean_stem = clean_stem[:-2]

    # 2. 识别编号后缀，例如 _01, _1, _02, _2
    num_tag = ""
    m_num = re.search(r"_(\d+)$", clean_stem)
    if m_num:
        num_tag = f" · {m_num.group(1)}"
        clean_stem = clean_stem[:m_num.start()]

    # 3. 查表匹配官方中文名（先全匹配，再不区分大小写匹配）
    cn_title = SCENE_CHINESE_NAMES.get(clean_stem)
    if not cn_title:
        clean_lower = clean_stem.lower()
        for k, v in SCENE_CHINESE_NAMES.items():
            if k.lower() == clean_lower:
                cn_title = v
                break

    # 4. 前缀回退匹配（例如 BrokenCrystal_1 -> 破碎的水晶遗址 · 1）
    if not cn_title:
        for k, v in SCENE_CHINESE_NAMES.items():
            if clean_stem.startswith(k):
                remainder = clean_stem[len(k):].lstrip("_")
                cn_title = f"{v} {remainder}".strip()
                break

    # 5. 若仍无匹配，按驼峰分词回退，保底可读
    if not cn_title:
        cn_title = clean_stem

    return f"{cn_title}{num_tag}{time_tag}"


def _classify(fn: str) -> str:
    """按关键词归类到场景分类（custom 分类不参与关键词匹配）。"""
    clean = _clean_str(fn)
    for c in CATEGORIES:
        if c["id"] == "custom":
            continue
        if any(_clean_str(kw) in clean for kw in c["keywords"]):
            return c["id"]
    return "wasteland_surface"


def _thumb_rel_path(filename: str, source: str = "official") -> str:
    """缩略图相对 resources/ 的路径（前端直接拼 assetUrl）。

    自定义背景用独立后缀，避免与同名官方背景抢同一张缩略图。
    """
    stem = Path(filename).stem
    if source == "custom":
        return f"thumbnails/background/{stem}{CUSTOM_THUMB_SUFFIX}.webp"
    return f"thumbnails/background/{stem}.webp"


def custom_thumb_name(filename: str) -> str:
    """自定义背景缩略图文件名（对外暴露，导入/删除共用）。"""
    return f"{Path(filename).stem}{CUSTOM_THUMB_SUFFIX}.webp"


def resolve_background_file(root: Path, filename: str) -> Path | None:
    """把背景文件名解析为磁盘上的实际文件。

    查找顺序：自定义(custom) → 官方(background) → 导出目录(output) → 超分预览(preview)。
    只取文件名部分，拒绝任何带路径分隔符的输入（防目录穿越）。
    """
    name = str(filename or "").replace("\\", "/").strip()
    if not name:
        return None
    name = name.rsplit("/", 1)[-1]
    if not name or name in (".", ".."):
        return None
    dirs = background_dirs(root)
    for directory in (dirs.custom, dirs.official, dirs.output, dirs.preview):
        p = directory / name
        if p.is_file():
            return p
    return None


def get_available_backgrounds(bg_dir: Path, custom_dir: Path | None = None) -> list[dict[str, Any]]:
    """扫描官方与自定义背景目录，返回统一格式的背景条目列表。

    每条含 source 字段（official / custom）。同名时自定义条目覆盖官方条目——
    与 resolve_background_file 的"自定义优先"一致，保证列表所见即实际上图。
    """
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    pairs: list[tuple[Path | None, str]] = [(custom_dir, "custom"), (bg_dir, "official")]
    for directory, source in pairs:
        if not directory or not directory.is_dir():
            continue
        for f in sorted(directory.iterdir()):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            if f.name in seen:
                continue
            seen.add(f.name)
            if source == "custom":
                ensure_thumbnail(directory, f.name, custom_thumb_name(f.name))
                results.append({
                    "filename": f.name,
                    "name": _friendly_name(f.name),
                    "category": "custom",
                    "thumb": _thumb_rel_path(f.name, "custom"),
                    "source": "custom",
                })
            else:
                # 官方缩略图缺失/被清理时自愈（正常情况下只做一次 stat）
                ensure_thumbnail(directory, f.name)
                results.append({
                    "filename": f.name,
                    "name": _friendly_name(f.name),
                    "category": _classify(f.name),
                    "thumb": _thumb_rel_path(f.name),
                    "source": "official",
                })

    # 自定义置顶（导入后立刻可见），其余按名称排序
    results.sort(key=lambda x: (x["source"] != "custom", x["name"].lower()))
    return results


def ensure_thumbnail(bg_dir: Path, filename: str, thumb_name: str | None = None) -> str:
    """确保指定背景图片的缩略图存在，若不存在自动生成 (320x180 WebP)。

    thumb_name 可显式指定缩略图文件名：自定义背景用独立后缀，避免与同名官方
    背景共用一张缩略图（否则自定义版本会显示官方缩略图，删除时又会误删官方缩略图）。
    """
    base_stem = Path(filename).stem
    thumb_dir = Path(bg_dir).parent / "thumbnails" / "background"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / (thumb_name or f"{base_stem}.webp")
    if not thumb_path.exists() or thumb_path.stat().st_size == 0:
        src_path = Path(bg_dir) / filename
        if src_path.exists():
            try:
                with Image.open(src_path) as im:
                    im.thumbnail((320, 180), Image.BILINEAR)
                    im.convert("RGB").save(thumb_path, "WEBP", quality=75)
            except Exception:
                return filename
    return thumb_path.name


def _file_digest(path: Path) -> str:
    """文件内容摘要，用于判断扩图成果是否与已导入的一致（避免重复导入）。"""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _matches_official(bg_dir: Path, name: str, candidate: Path) -> bool:
    """中转文件是否与同名官方背景内容一致（即"导出后原样丢回来、还没扩图"）。"""
    official = Path(bg_dir) / name
    if not official.is_file():
        return False
    try:
        return _file_digest(official) == _file_digest(candidate)
    except Exception:  # noqa: BLE001
        return False


def _outpaint_readme() -> str:
    return (
        "扩图工作流说明（本文件夹 = output 导出目录）\r\n"
        "================================================\r\n"
        "1) 在软件里选好背景，点「📤 导出扩图」——当前背景（含已超分版本）会复制到本文件夹；\r\n"
        "2) 用 Photoshop 生成式扩展 / Stable Diffusion 等工具把画面扩到目标比例；\r\n"
        "3) 把做好的成品放进软件资源目录下的 input 文件夹（png/jpg/webp/bmp 均可，\r\n"
        "   文件名随意，非 png 导入时会自动转成 png）；\r\n"
        "4) 回到软件点「📥 导入扩图」——input 里的图片会转入自定义背景库，\r\n"
        "   在「自定义 / 扩图」分类里即可选中、超分、合成、导出壁纸。\r\n"
        "\r\n"
        "注意：只有 input 文件夹里的图片会被导入，本文件夹（output）不会被扫描。\r\n"
    )


def export_background_for_outpaint(root: Path, filename: str) -> dict:
    """把当前所选背景复制到导出目录(output)，供外部工具扩图。

    只负责导出与准备目录，不打开资源管理器（由前端单独的"打开目录"按钮触发）。
    """
    src = resolve_background_file(root, filename)
    if src is None:
        raise FileNotFoundError(f"背景原图不存在：{filename}")

    dirs = background_dirs(root)
    dirs.output.mkdir(parents=True, exist_ok=True)
    # 同时建好 input，用户扩图完就有地方放成品，不用自己找路径
    dirs.input.mkdir(parents=True, exist_ok=True)

    dest = dirs.output / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)

    readme = dirs.output / "扩图说明.txt"
    if not readme.exists():
        try:
            readme.write_text(_outpaint_readme(), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    return {
        "ok": True,
        "filename": dest.name,
        "source": str(src),
        "dir": str(dirs.output),
        "inputDir": str(dirs.input),
        "message": f"已导出到 output：{dest.name}（扩图完成后把成品放进 input，再点「导入扩图」）",
    }


def import_outpaint_results(root: Path) -> dict:
    """把导入目录(input)里的图片收进自定义背景库（非 png 自动转 png 并生成缩略图）。

    只扫描 input——output 里是待扩图的原始导出，不参与导入。
    同名文件内容一致则跳过（视为已导入）；内容不同则覆盖（视为对同一张扩图的修正）。
    """
    dirs = background_dirs(root)
    bg_dir, custom_dir, input_dir, preview_dir = dirs.official, dirs.custom, dirs.input, dirs.preview
    custom_dir.mkdir(parents=True, exist_ok=True)

    imported: list[str] = []
    skipped: list[str] = []
    unchanged: list[str] = []
    failed: list[str] = []
    # 本轮已处理的目标文件名：png 与同名 jpg 会映射到同一个目标，后者按重复跳过
    handled: set[str] = set()

    if not input_dir.is_dir():
        return {
            "ok": True,
            "imported": [],
            "skipped": [],
            "unchanged": [],
            "failed": [],
            "count": 0,
            "dir": str(custom_dir),
            "message": "input 文件夹为空：请先把扩图成品放进 input（导出目录是 output，不会被扫描）",
        }

    for f in sorted(input_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
            continue
        tmp_path: Path | None = None
        try:
            dest = custom_dir / f.name
            if f.suffix.lower() != ".png":
                # 超分引擎只接受 png：导入时统一转存为 png，避免后续无法超分/导出。
                # 先转到临时文件再与目标比对内容，重复导入才是幂等的
                # （同一张图 png/jpg 两份存在时不会每次都重写）。
                dest = custom_dir / (f.stem + ".png")
                if dest.name in handled:
                    skipped.append(dest.name)
                    continue
                preview_dir.mkdir(parents=True, exist_ok=True)
                tmp_path = preview_dir / f"._import_{dest.name}"
                with Image.open(f) as im:
                    im.convert("RGBA" if "A" in im.getbands() else "RGB").save(tmp_path, "PNG")
                if _matches_official(bg_dir, dest.name, tmp_path):
                    unchanged.append(dest.name)
                    handled.add(dest.name)
                    continue
                if dest.exists() and _file_digest(dest) == _file_digest(tmp_path):
                    skipped.append(dest.name)
                    handled.add(dest.name)
                    continue
                tmp_path.replace(dest)
                tmp_path = None
            else:
                if dest.name in handled:
                    skipped.append(dest.name)
                    continue
                if _matches_official(bg_dir, dest.name, f):
                    # 导出后原样丢回来的副本（还没扩图）：导入只会多出一份同名遮罩，跳过
                    unchanged.append(dest.name)
                    handled.add(dest.name)
                    continue
                if dest.exists() and _file_digest(dest) == _file_digest(f):
                    skipped.append(dest.name)
                    handled.add(dest.name)
                    continue
                if f.resolve() != dest.resolve():
                    shutil.copy2(f, dest)
            handled.add(dest.name)
            ensure_thumbnail(custom_dir, dest.name, custom_thumb_name(dest.name))
            imported.append(dest.name)
        except Exception:  # noqa: BLE001
            failed.append(f.name)
        finally:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:  # noqa: BLE001
                    pass

    if imported:
        message = f"已从 input 导入 {len(imported)} 张扩图背景，可在「自定义 / 扩图」分类中选用"
        if unchanged:
            message += f"；另有 {len(unchanged)} 张与官方原图一致（还没扩图）已跳过"
    elif unchanged:
        message = f"input 里有 {len(unchanged)} 张图片与官方原图完全一致（还没扩图），已跳过"
    elif skipped:
        message = "input 中的图片均已导入过，无需重复导入"
    else:
        message = "input 文件夹中没有可导入的图片"
    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
        "unchanged": unchanged,
        "failed": failed,
        "count": len(imported),
        "dir": str(custom_dir),
        "message": message,
    }


def delete_custom_background(root: Path, filename: str) -> dict:
    """删除一张自定义背景（连同缩略图）；同名官方背景会自动重新可见。"""
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    dirs = background_dirs(root)
    custom_dir, official_dir = dirs.custom, dirs.official
    target = custom_dir / name
    if not name or not target.is_file():
        return {"ok": False, "error": f"自定义背景不存在：{filename}"}

    target.unlink()
    thumb = custom_dir.parent / "thumbnails" / "background" / custom_thumb_name(target.name)
    try:
        if thumb.is_file():
            thumb.unlink()
    except Exception:  # noqa: BLE001
        pass
    # 同名官方背景的缩略图若被清理过，顺带自愈；官方背景本身一直还在，删除自定义后即重新可见
    official = official_dir / name
    if official.is_file():
        try:
            ensure_thumbnail(official_dir, name)
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "filename": name, "message": f"已删除自定义背景：{name}"}



def get_recommendations_for_ship(
    ship_name: str,
    available_filenames: set[str],
) -> list[str]:
    """为特定角色推荐背景文件名列表（只返回本地实际存在的背景）。"""
    s_lower = ship_name.lower().strip()
    s_clean = _clean_str(ship_name)

    rec_keys = []
    # 1. 尝试直接查 CHARACTER_RECOMMENDED_BACKGROUNDS
    for k, bgs in CHARACTER_RECOMMENDED_BACKGROUNDS.items():
        if k in s_lower or _clean_str(k) in s_clean:
            rec_keys.extend(bgs)

    # 2. 尝试从中文名查英文键
    if not rec_keys:
        for cn_k, en_k in CN_TO_EN_KEY.items():
            if cn_k in ship_name:
                rec_keys.extend(CHARACTER_RECOMMENDED_BACKGROUNDS.get(en_k, []))

    # 3. 皮肤关键词推导（如泳装 Summer/Beach/Ocean，圣诞/雪 Winter/Snow）
    if any(w in s_lower for w in ["summer", "beach", "ocean", "swim", "水着", "泳装", "蓝色海洋"]):
        rec_keys.extend(["CleanBeach.png", "PinkBeachIsland_d.png", "BluewaterIsland.png", "Beach_d.png"])
    if any(w in s_lower for w in ["winter", "snow", "xmas", "christmas", "温泉", "冬", "雪"]):
        rec_keys.extend(["HotSpringInnIn_d.png", "BigHotSpring_d.png", "Winter_AmusementPark.png", "SnowTown_d.png"])
    if any(w in s_lower for w in ["bunny", "rabbit", "兔女郎"]):
        rec_keys.extend(["CoinRushMainHall.png", "CoinRushGameZone.png", "Stage.png"])

    # 默认兜底：前哨基地与方舟指挥官室
    rec_keys.extend(["CommanderRoom.png", "Ark.png", "OutpostOut.png"])

    # 过滤去重并确保本地存在
    final_recs = []
    seen = set()
    for fn in rec_keys:
        if fn in available_filenames and fn not in seen:
            seen.add(fn)
            final_recs.append(fn)

    return final_recs
