# 我的世界原版翻译风格规范

本文件约定术语表之外的按域构词体例、语序变化、整类不译与全局标点间距规则。单个词条译名查 `Vanilla/terms/` 下的术语表，旧版本译名差异查 `terms-version.tsv`。

## 1. 方块、物品与实体
<!-- @scope {"id": "scope.block_item", "include": ["block.minecraft.*", "item.minecraft.*", "entity.minecraft.*"]} -->

### 1.1 修饰词与助词「的」

#### 深板岩与深层

- `Deepslate` 作矿石定语（`Deepslate ... Ore`）译作 `深层`，如 `Deepslate Diamond Ore` → `深层钻石矿石`。
- 其余方块与制品一律译作 `深板岩`，如 `Deepslate Bricks` → `深板岩砖`。

#### 氧化铜与涂蜡

- `Exposed`（斑驳）、`Weathered`（锈蚀）、`Oxidized`（氧化）或 `Waxed`（涂蜡）单独修饰铜制品时均带「的」，如 `Exposed Copper` → `斑驳的铜块`、`Waxed Copper Bulb` → `涂蜡的铜灯`。
- `Waxed` 与氧化度叠加时只保留外层「的」，如 `Waxed Exposed Copper` → `涂蜡的斑驳铜块`。

#### 可疑的

- `Suspicious <方块>` 保留「的」，如 `Suspicious Sand` → `可疑的沙子`。
- 特例：`Suspicious Stew` → `谜之炖菜`。

#### 粗金属、生肉与失活珊瑚

- `Raw Iron/Gold/Copper` 系列译作 `粗<金属>`，不加「的」，如 `Raw Iron` → `粗铁`。
- 生肉与生鱼类（`Raw Beef`、`Raw Cod` 等）译作 `生…`。
- `Dead <... Coral>` 一律带「的」，译作 `失活的<...珊瑚>`（挂墙叠加规则见 1.4）。

#### 材料块倒装

- `Block of <X>` 倒装并省去「之/的」，写作 `<X>块`，如 `Block of Copper` → `铜块`、`Block of Raw Iron` → `粗铁块`、`Block of Stripped Bamboo` → `去皮竹块`。
- 叠加外层 `Waxed` 时写作 `涂蜡的铜块`。

#### 装填炼药锅

- `<物质> Cauldron` 译作 `装有<物质>的炼药锅`，如 `Water Cauldron` → `装有水的炼药锅`、`Powder Snow Cauldron` → `装有细雪的炼药锅`。

#### 固定不加「的」的加工与状态前缀

- `Stripped`（`去皮…`）、`Polished`（`磨制…`）、`Cracked`（`裂纹…`）、`Cut`（`切制…`）、`Smooth`（`平滑…`）、`Infested`（`虫蚀…`）、`Chiseled`（`雕纹…`）。
- `Mossy` 译作 `苔…`，其中 `Mossy Cobblestone` 同步省去「圆」字，译作 `苔石`（衍生为 `苔石台阶/楼梯/墙`）；`Mossy Stone Bricks` 译作 `苔石砖`。

### 1.2 树木、木材与竹子

#### 单字树根（`Oak` 橡、`Dark Oak` 深色橡、`Pale Oak` 苍白橡、`Poplar` 杨）

- 树叶与树苗补「树」：`<X>树树叶`、`<X>树树苗`，如 `Oak Leaves` → `橡树树叶`、`Dark Oak Sapling` → `深色橡树树苗`。
- 原木、木板、木材与制品补「木」：`<X>木原木`、`<X>木木板`、`<X>木<制品>`，如 `Oak Planks` → `橡木木板`、`Poplar Shelf` → `杨木展示架`。
- `<Tree> Wood` 译作 `<X>木`，如 `Pale Oak Wood` → `苍白橡木`、`Poplar Wood` → `杨木`。

#### 多字树名（`Spruce` 云杉、`Birch` 白桦、`Jungle` 丛林、`Acacia` 金合欢、`Cherry` 樱花、`Mangrove` 红树、`Crimson` 绯红、`Warped` 诡异）

- 自带部位或材质语素的专属部件（`Leaves` 树叶、`Sapling` 树苗、`Log` 原木、`Planks` 木板、`Propagule` 胎生苗、`Roots` 根、`Stem` 菌柄、`Hyphae` 菌核）直拼基础名，如 `云杉树叶`、`云杉木板`、`红树根`、`绯红菌柄`、`诡异菌核`。
- `<Tree> Wood` 及门、船、台阶、栅栏、展示架等通用制品在基础名后加「木」，写作 `<X>木` 或 `<X>木<制品>`，如 `云杉木`、`金合欢木船`、`红树木展示架`、`诡异木活板门`。

#### 竹（`Bamboo`，非木材）

- 独立物品与盆栽用 `竹子`（`竹子`、`竹子盆栽`）。
- 制品前缀统一减为单字 `竹`，如 `竹块`、`竹门`、`竹筏`、`竹马赛克`、`竹展示架`。
- 特例：`Bamboo Planks` → `竹板`、`Bamboo Shoot`（`bamboo_sapling`）→ `竹笋`。

#### 悬挂式告示牌

- `<Tree> Hanging Sign` 将 `悬挂式` 前置，写作 `悬挂式<X>木告示牌`；竹类写作 `悬挂式竹告示牌`。

### 1.3 高歧义通名（砖、石、桶、盔甲）

#### 砖与砖块（`Brick` / `Bricks`）

- 独立红砖物品 `Brick` → `红砖`，方块 `Bricks` → `红砖块`，衍生 `Brick Slab/Stairs/Wall` → `红砖台阶/楼梯/墙`。
- 复合词定语 `Brick` 统一译作 `砖`，如 `Nether Brick` → `下界砖`、`Deepslate Brick Slab` → `深板岩砖台阶`。
- 复数 `Bricks` 若存在同名单片砖物品则译作 `砖块`（`Nether Bricks` → `下界砖块`、`Red Nether Bricks` → `红色下界砖块`、`Resin Bricks` → `树脂砖块`）。
- 否则一律译作 `砖`（`Stone Bricks` → `石砖`、`Deepslate Bricks` → `深板岩砖`、`Mud Bricks` → `泥砖`、`Tuff Bricks` → `凝灰岩砖`、`Prismarine Bricks` → `海晶石砖`、`Quartz Bricks` → `石英砖`、`Cinnabar Bricks` → `朱砂砖`、`Sulfur Bricks` → `硫黄砖`）。

#### 石头与石质（独立词素 `Stone`）

- 独立方块 `Stone` 及其常规方块变体（`Stone Slab/Stairs/Button/Pressure Plate`、`Smooth Stone`、`Infested Stone`）用 `石头`。
- 石质工具武器（`Stone Sword/Pickaxe/Axe/Shovel/Hoe/Spear` → `石剑/石镐/石斧/石锹/石锄/石矛`）及复合砖石词素（`Stone Bricks` → `石砖`、`End Stone` → `末地石`）减字为 `石`。

#### 桶（`Bucket`）

- 空桶 `Bucket` → `铁桶`；装填液体、粉雪或生物的复合桶统一用 `桶`，如 `Water Bucket` → `水桶`、`Powder Snow Bucket` → `细雪桶`、`Bucket of Axolotl` → `美西螈桶`。
- `Milk` 作 `奶`，`Milk Bucket` → `奶桶`。

#### 盔甲与挽具（`Armor` / `Harness`）

- 玩家装备、纹饰与常规语境用 `盔甲`，如 `Armor Stand` → `盔甲架`。
- 坐骑与动物护甲用 `…铠`，如 `Horse Armor` → `马铠`、`Wolf Armor` → `狼铠`、`Nautilus Armor` → `鹦鹉螺铠`。
- `Harness` 译作 `挽具`，带色变体写作 `<颜色>挽具`。

### 1.4 附着、容器、刷怪蛋与载体

#### 墙上附着方块

- key 含 `wall_sign`、`wall_hanging_sign`、`wall_torch`、`wall_fan`、`wall_head`、`wall_skull` 时统一前置 `墙上的`，如 `Wall Torch` → `墙上的火把`、`Acacia Wall Hanging Sign` → `墙上的悬挂式金合欢木告示牌`。
- 珊瑚扇同时叠加「失活」与「墙上」时省去内层「的」，如 `Dead Brain Coral Wall Fan` → `墙上的失活脑纹珊瑚扇`。
- 末尾为 `Wall` 的独立石墙/砖墙方块译作 `<X>墙`，如 `Andesite Wall` → `安山岩墙`。

#### 生物与玩家头颅（不含 `Piston Head` 活塞头）

- `Skeleton/Wither Skeleton Skull` → `<生物>头颅`、`Dragon Head` → `龙首`。
- `Creeper/Piglin/Player/Zombie Head` → `<生物>的头`（`%s's Head` → `%s的头`）；挂墙时前置 `墙上的`。

#### 盆栽与蜡烛蛋糕

- `potted_*`（`Potted <Plant>`）译作 `<植物>盆栽`，不加「盆栽的」，如 `Potted Allium` → `绒球葱盆栽`。
- `Cake with Candle` → `插上蜡烛的蛋糕`，带色变体写作 `插上<颜色>蜡烛的蛋糕`。

#### 刷怪蛋

- `*_spawn_egg`（`<Mob> Spawn Egg`）统一译作 `<生物>刷怪蛋`。

#### 运输与载体

- 带箱船将 `运输` 置于木种与 `船` 之间：`<Tree> Boat with Chest` → `<木种>运输船`（如 `Oak Boat with Chest` → `橡木运输船`），无木种 `Boat with Chest` → `运输船`。
- 运输矿车与竹筏前置 `运输`：`Minecart with Chest` → `运输矿车`、`Bamboo Raft with Chest` → `运输竹筏`。
- 其余载物矿车：`Minecart with Furnace` → `动力矿车`、`Minecart with Monster Spawner` → `刷怪笼矿车`，其余译作 `<载物>矿车`（如 `Minecart with TNT` → `TNT矿车`、`Minecart with Hopper` → `漏斗矿车`）。

## 2. 特殊制品域

### 2.1 旗帜图案
<!-- @scope {"id": "scope.banner", "include": ["block.minecraft.banner.*", "item.minecraft.*_banner_pattern", "item.minecraft.*_banner_pattern.*"]} -->

#### 颜色嵌槽总则

- 16 种颜色在下列去「色」格局以及 `Cross`、`Saltire`、`Paly` 中一律省去「色」字，单字色（`黑`、`白`）与双字色（`淡蓝`、`淡灰`、`黄绿`、`品红`、`粉红`）同规。
- 其余格局一律采用 `<颜色>色<图案>` 前置。

#### 去「色」嵌槽与固定格局（`<C>` 为去「色」颜色名，如 `黑`、`淡蓝`）

- 满底：`Fully <C> Field` → `<C>底`。
- 横条：`Base` → `底<C>横条`、`Fess` → `中<C>横条`、`Chief` → `顶<C>横条`。
- 竖条：`Pale` → `中<C>竖条`、`Pale Dexter` → `右<C>竖条`、`Pale Sinister` → `左<C>竖条`。
- 斜条：`Bend` → `右<C>斜条`、`Bend Sinister` → `左<C>斜条`。
- 方角：`Base Dexter Canton` → `右底<C>方`、`Base Sinister Canton` → `左底<C>方`、`Chief Dexter Canton` → `右顶<C>方`、`Chief Sinister Canton` → `左顶<C>方`。
- 三角：`Chevron` → `底<C>三角`、`Inverted Chevron` → `顶<C>三角`。
- 十字与条纹：`Cross` → `<C>正十字`、`Saltire` → `<C>斜十字`、`Paly` → `<C>竖条纹`。

#### 保留 `<颜色>色` 前置的格局

- 边框与波纹：`Bordure`（方框边）、`Bordure Indented`（波纹边）、`Base Indented`（底波纹）、`Chief Indented`（顶波纹）。
- 几何与渐淡：`Field Masoned`（砖纹）、`Roundel`（圆形）、`Lozenge`（菱形）、`Gradient`（自上渐淡）、`Base Gradient`（自下渐淡）。
- 对半与斜分：`Per Fess`（上半方形）、`Per Fess Inverted`（下半方形）、`Per Pale`（右半方形）、`Per Pale Inverted`（左半方形）、`Per Bend`（左上三角）、`Per Bend Sinister`（右上三角）、`Per Bend Inverted`（右下三角）、`Per Bend Sinister Inverted`（左下三角）。
- 徽章图案：`Creeper Charge`（苦力怕盾徽）、`Flower Charge`（花朵盾徽）、`Skull Charge`（头颅盾徽）、`Thing`（`Mojang徽标`）、`Snout`（猪鼻）、`Globe`（地球）、`Flow`（涡流）、`Guster`（旋风）。

#### 旗帜图案物品

- 本体泛称 `Banner Pattern` → `旗帜图案`。
- 带图案名的物品（`<Pattern> Banner Pattern`）译作 `<图案>旗帜图案`，如 `Field Masoned Banner Pattern` → `砖纹旗帜图案`、`Thing Banner Pattern` → `Mojang徽标旗帜图案`。
- `.desc` 仅写 `<图案>` 名。

### 2.2 陶片与盔甲纹饰
<!-- @scope {"id": "scope.pottery_trim", "include": ["item.minecraft.*_pottery_sherd", "item.minecraft.*_pottery_shard", "item.minecraft.pottery_shard_*", "item.minecraft.*_armor_trim_smithing_template", "item.minecraft.*_armor_trim_smithing_template.*", "item.minecraft.smithing_template.armor_trim.*", "trim_pattern.*", "trim_material.*"]} -->

#### 陶片与纹饰构词

- 纹样陶片统一译作 `<纹样>纹样陶片`。
- 锻造模板泛称 `Smithing Template` → `锻造模板`；带纹样名的盔甲纹饰（`<Pattern> Armor Trim`）译作 `<纹样>盔甲纹饰`。
- 纹饰材料 `<X> Material` 译作 `<X>质`，如 `Amethyst Material` → `紫水晶质`。

#### 隔离分表查表原则

- 纹样词干按所属 `special/` 分表取值，不混用通用词表：如 `Flow` 在陶片、盔甲纹饰与旗帜中均为 `涡流`；`Explorer` 在陶片中为 `探险`，在地图中为 `探险家`。

### 2.3 药水与药箭
<!-- @scope {"id": "scope.potion", "include": ["item.minecraft.potion.effect.*", "item.minecraft.splash_potion.effect.*", "item.minecraft.lingering_potion.effect.*", "item.minecraft.tipped_arrow.effect.*"]} -->

#### 常规构词

- `Potion of <Effect>` → `<效果>药水`；喷溅型与滞留型分别前置 `喷溅型`、`滞留型`。
- 药箭 `Arrow of <Effect>` → `<效果>之箭`。

#### 与状态效果异名的药水定名

- `Infestation` → `虫蚀`（效果 `Infested` 为 `寄生`）
- `Poison` → `剧毒`（效果为 `中毒`）
- `Regeneration` → `再生`（效果为 `生命恢复`）
- `Slowness` → `迟缓`（效果为 `缓慢`）
- `Water Breathing` → `水肺`（效果为 `水下呼吸`）
- `the Turtle Master` → `神龟`

#### 基础与不可合成系列

- `Water Bottle` → `水瓶`（`喷溅型水瓶`、`滞留型水瓶`）、`Arrow of Splashing` → `喷溅之箭`。
- `Awkward` → `粗制的药水`、`Mundane` → `平凡的药水`、`Thick` → `浓稠的药水`（喷溅/滞留型直接前置 `喷溅型`/`滞留型`，如 `喷溅型粗制的药水`）；对应的未定型药箭均译作 `药箭`。
- `Uncraftable` 系列写作 `不可合成的药水`、`不可合成的药箭`；叠加喷溅/滞留型时 `不可合成的` 置于最前，写作 `不可合成的喷溅型药水`、`不可合成的滞留型药水`。

## 3. 域外特例

### 3.1 生物群系
<!-- @scope {"id": "scope.biome", "include": ["biome.minecraft.*"]} -->

#### 树种与林地特例（全量见 `terms-biome.tsv`）

- `Birch Forest` 省「白」，译作 `桦木森林`；`Old Growth Birch Forest` → `原始桦木森林`。
- `Old Growth Pine Taiga` → `原始松木针叶林`；`Mangrove Swamp` → `红树林沼泽`。
- `Bamboo Jungle` 减字译作 `竹林`；`Cherry Grove` → `樱花树林`（对照 `Grove` → `雪林`）。

### 3.2 属性
<!-- @scope {"id": "scope.attribute", "include": ["attribute.name.*"]} -->

#### 跨域用词切换（全量见 `terms-tech.tsv`）

- `Armor` → `护甲值`、`Armor Toughness` → `盔甲韧性`。
- `Luck` → `幸运值`（状态效果为 `幸运`）；`Speed` → `速度`（状态效果为 `迅捷`）。

### 3.3 魔咒诅咒
<!-- @scope {"id": "scope.enchantment", "include": ["enchantment.minecraft.*"]} -->

#### 诅咒倒装（全量见 `terms-enchantment.tsv`）

- `Curse of <X>` 倒装译作 `<X>诅咒`，如 `Curse of Binding` → `绑定诅咒`、`Curse of Vanishing` → `消失诅咒`。

### 3.4 已填充地图
<!-- @scope {"id": "scope.filled_map", "include": ["filled_map.*", "item.minecraft.*_map"]} -->

#### 探险家、藏宝与结构地图

- `<Location> Explorer Map` → `<地点>探险家地图`（`Woodland` → `林地探险家地图`、`Ocean` → `海洋探险家地图`、`Trial` → `试炼探险家地图`）。
- `Buried Treasure Map` → `藏宝图`；其余 `Buried <地点> Map` 译作 `埋藏的<地点>地图`（如 `Buried Ancient City Map` → `埋藏的远古城市地图`）。
- 其余结构与营地地图译作 `<地点>地图`，如 `Jungle Temple Map` → `丛林神庙地图`、`Birch Forest Camp Map` → `桦木森林营地地图`。

#### 缩放与编号

- `Scaling at 1:%s` → `比例尺1:%s`、`(Level %s/%s)` → `（缩放等级%s/%s）`、`ID #%s` → `ID #%s`。

## 4. 唱片、音乐与画作
<!-- @scope {"id": "scope.media", "include": ["item.minecraft.music_disc_*.desc", "item.minecraft.disc_fragment_*.desc", "jukebox_song.*", "music.*", "painting.minecraft.*.title", "painting.minecraft.*.author"]} -->

### 4.1 唱片与音乐

#### 曲名与作者

- 音乐唱片与背景音乐曲名保留英文原文。
- 作者通常保留原文，唯日本作曲家 `Kumi Tanioka` 在 `music.game.*` 中译作 `谷冈久美`，如 `谷冈久美 - An Ordinary Day`、`谷冈久美 - komorebi`。

#### 版本括注与唱片残片

- 曲名后的版本或乐器括注译出并改用全角括号，如 `Lena Raine - Creator (Music Box)` → `Lena Raine - Creator（八音盒）`。
- 唱片残片描述 `item.minecraft.disc_fragment_5.desc`（`Music Disc - 5`）译作 `音乐唱片 - 5`。

### 4.2 画作

#### 标题与作者

- 画作标题与作者保留原语言原文，如 `Albanian`、`de_aztec`、`Kristoffer Zetterstrand`。

## 5. 功能文本

### 5.1 字幕
<!-- @scope {"id": "scope.subtitles", "include": ["subtitles.*"]} -->

#### 有主体音效

- 写作 `<发声主体>：<动作或声音>`，全角冒号 `：` 后不留空格，如 `Amethyst chimes` → `紫水晶：叮铃`。
- 按中文自然动作调整语序或意译交互语义，如 `Bee leaves hive` → `蜜蜂：离巢`、`Goat Horn breaks off` → `山羊：断角`、`Lever clicks` → `拉杆：拉动`。

#### 无主体环境音

- 直接写名词或动宾短语，如 `Eerie noise` → `怪异的噪声`、`Splashing` → `溅起水花`。

### 5.2 统计项
<!-- @scope {"id": "scope.stat", "include": ["stat.*"]} -->

#### 统计收尾格式

- 次数类收尾用 `…次数`，如 `Animals Bred` → `繁殖动物次数`。
- 距离类收尾用 `…距离`，如 `Distance by Boat` → `坐船移动距离`；特例 `Distance Fallen` → `摔落高度`。
- 数量与伤害量分别用 `…数` 与 `…量`，如 `Fish Caught` → `捕鱼数`、`Damage Dealt` → `造成伤害量`。
- 时长与间隔写作 `…时长`、`…时间` 或 `自上次…`，如 `Time Played` → `游戏时长`、`Sneak Time` → `潜行时间`、`Time Since Last Death` → `自上次死亡`。

### 5.3 死亡消息
<!-- @scope {"id": "scope.death", "include": ["death.*"]} -->

#### 句式与标点

- 保持紧凑陈述句，句末不加句号，如 `%1$s was shot by %2$s` → `%1$s被%2$s射杀`。

### 5.4 进度
<!-- @scope {"id": "scope.advancements", "include": ["advancements.*"]} -->

#### 标题与描述

- 标题偏四字或简练名词性短语。
- 描述多用无主语祈使短语，单句陈述句末不加句号，如 `Discover every biome` → `发现所有的生物群系`；问句、感叹句、省略号及含 `\n注：` 的多行附注保留对应标点。

### 5.5 游戏规则与选项
<!-- @scope {"id": "scope.options_gamerule", "include": ["gamerule.*", "options.*"]} -->

#### 游戏规则

- `gamerule` 规则名不加句号；`.description` 完整说明句末一律加全角句号 `。`。

#### 设置选项

- `options.*` 键值展示使用全角冒号 `：` 且不留空格，如 `聊天延迟：%s秒`、`%s：开`。
- 完整句 `.tooltip` / `.description` 句末加全角句号 `。`，短标签式提示（如 `辅助功能设置`、`更改语言`）不加。

### 5.6 键盘按键
<!-- @scope {"id": "scope.keyboard", "include": ["key.keyboard.*"]} -->

#### 保留英文原文

- 常用控制键、修饰键与功能键保留英文原文（`Backspace`、`Caps Lock`、`Delete`、`End`、`Enter`、`Home`、`Insert`、`Num Lock`、`Page Down`、`Page Up`、`Pause`、`Print Screen`、`Scroll Lock`、`Tab`、`F1`–`F25` 等；`Escape` 简写为 `Esc`）。

#### 修饰键、方向键与空格

- 左右修饰键前置 `左`/`右` 且不留空格，如 `Left Alt` → `左Alt`、`Left Control` → `左Ctrl`、`Right Shift` → `右Shift`。
- 方向键译作 `上/下/左/右方向键`；`Space` 译作 `空格`。

#### 编号与前缀键

- 前缀后留一个半角空格：`AC <Action>` → `AC <动作>`（如 `AC 后退`）、`Keypad <X>` → `小键盘 <X>`（如 `小键盘 0`、`小键盘 Enter`）、`International <N>` → `国际键 <N>`、`Language <N>` → `语言键 <N>`。

## 6. 全局策略
<!-- @scope {"id": "global", "apply": "always"} -->

### 6.1 查表与体例分工

#### 规则与术语表边界

- 本文件规定依赖语境删字、改序、嵌槽、加减「的」、整类不译及标点间距规则。
- 单个词条与不译词（如 `TNT`）查 `terms-v1.tsv` 与六张域分表；特定域冲突词条查 `special/` 隔离分表；历史版本译名差异查 `terms-version.tsv`。

### 6.2 全局不译与专名

#### 品牌与产品专名

- `Minecraft`、`Minecraft Realms`、`Realms`、`Mojang` 保留英文原文。
- 指代整项服务多作 `Realms`，指代单个领域或列表名常去复数作 `Realm`（如 `返回到Realm列表`、`正在还原你的Realm`）；旗帜图案中保留 `Mojang徽标`。

#### 罗马数字等级

- 附魔等级（`enchantment.level.*`）与药水等级（`potion.potency.*`）统一保留罗马数字 `I`、`II`、`III`、`IV` 等，不改为阿拉伯数字或中文数字。

### 6.3 标点与间距

#### 中西文与占位符间距

- 常规中文与英文词、数字及 `%s`、`%1$s` 等占位符之间不加空格，如 `TNT爆炸已禁用`、`%1$s被%2$s射杀`、`自定义Boss栏%s现为可见`、`比例尺1:%s`、`显示macOS菜单栏`。

#### 空格例外

- 署名与单位串（`%1$s 著`、`%s fps`）、带前缀的按键名（`AC 后退`、`小键盘 0`、`国际键 1`、`语言键 1`）、组合键 `+` 两侧（`Control + 左键单击`、`Alt + F4`、`Cmd + Q`）以及斜杠进度/耐久度（`%s / %s`）保留半角空格。

#### 全角标点与乘号

- 说明性冒号、括号、引号统一用全角（`：`、`（）`、`“”`）；引用命令时外层用全角双引号、命令本身保持半角，如 `“/perf stop”`。
- 分辨率、尺寸与倍率统一用全角乘号 `×` 替代英文 `x`，如 `3×3（快）`、`%s×%s@%sHz`、`%s × %s`、`%s×`。
