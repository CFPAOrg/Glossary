# 我的世界原版翻译风格规范

本文件约定术语表之外的构词体例、语序变化、整类不译与全局标点间距规则。单个词条译名查 `Vanilla/terms/` 下的术语表，旧版本译名差异查 `terms-version.tsv`。

## 全局体例
<!-- @scope {"id": "global", "apply": "always"} -->

### 品牌与产品专名

- `Minecraft`、`Minecraft Realms`、`Realms`、`Mojang` 保留英文原文。
- 指代整项服务作 `Realms`，指代单个领域或列表名去复数作 `Realm`（如 `返回到Realm列表`）。
- 旗帜图案中保留 `Mojang徽标`。

### 数字与计量单位

- 附魔等级（`enchantment.level.*`）与药水等级（`potion.potency.*`）保留罗马数字 `I`、`II`、`III`、`IV` 等。
- 国际/现实物理单位（`km`、`ms`、`s`）及 `tick` 译作中文（`千米`、`毫秒`、`秒`、`刻`）且不加空格，如 `7千米`、`%s刻`。

### 空格与间距

- 常规中文与英文词、数字、占位符（`%s`、`%1$s` 等）及标点之间不加空格，如 `TNT爆炸已禁用`、`%1$s被%2$s射杀`、`比例尺1:%s`。
- 以下情形保留半角空格：署名与单位串（`%1$s 著`、`%s fps`）、带前缀按键名（`AC 后退`、`小键盘 0`）、组合键 `+` 两侧（`Alt + F4`、`Control + 左键单击`）以及斜杠进度/耐久度（`%s / %s`）。

### 标点与符号

- 说明性冒号、括号、引号统一用全角（`：`、`（）`、`“”`）。
- 英文单引号占位符 `'%s'` 转为全角双引号 `“%s”`。
- 引用命令时外层用全角双引号，命令本身保持半角（`“/perf stop”`）。
- 方括号保留半角 `[]`（`[调试]：`）。
- 分辨率、尺寸与倍率统一用全角乘号 `×` 替代 `x`（`3×3（快）`、`%s×`）。
- 界面按钮、加载状态与截断提示用单省略号 `…`（`辅助功能设置…`），完整叙述句用双省略号 `……`。

### 命令语法

- 命令本身（如 `/time`）与字面量关键字（如 `set|add|query`）保留英文原文，仅译描述性参数名，如 `/time <set|add|query> <值>`。

### 界面与操作表述

- 列表截断提示 `and %s more...` 固定译作 `还有%s项未显示…`。
- 占比与序号 `%s out of %s` 及计数语境 `%s/%s` 拆成逗号两段，作 `……%s<量词>，共%s<量词>`，如 `有%s个包下载失败，共%s个包`、`已选中%s条消息，共%s条`。
- 游戏动作（`Sneak`、`Interact`、`Reload` 等）译作对应行为，不译为具体按键。
- 鼠标操作 `Left/Right Click` 译作 `单击鼠标左键`/`单击鼠标右键`（或 `左键单击`/`右键单击`），`左键`/`右键` 仅用于 `key.mouse.*`。
- 正文提及键盘功能键名保留英文并首字母大写（`Shift`、`Ctrl`、`Alt`、`Esc`）。

## 基础方块、物品与实体
<!-- @scope {"id": "scope.block_item", "include": ["block.minecraft.*", "item.minecraft.*", "entity.minecraft.*", "item.modifiers.*"]} -->

### 铜制品的氧化与涂蜡

- `Exposed`（斑驳）、`Weathered`（锈蚀）、`Oxidized`（氧化）或 `Waxed`（涂蜡）单独修饰铜制品时均带“的”，如 `Exposed Copper` → `斑驳的铜块`、`Waxed Copper Bulb` → `涂蜡的铜灯`。
- `Waxed` 与氧化度叠加时只保留外层“的”，如 `Waxed Exposed Copper` → `涂蜡的斑驳铜块`。
- 除物品 `Raw Copper`（`粗铜`）外，以 `Copper` 结尾的方块即使不含 `Block of` 也补“块”，如 `Cut Copper` → `切制铜块`、`Chiseled Copper` → `雕纹铜块`。
- `Cut Copper Slab/Stairs` 系列省去“块”，如 `Cut Copper Slab` → `切制铜台阶`。

### 可疑的方块

- `Suspicious <方块>` 保留“的”，如 `Suspicious Sand` → `可疑的沙子`。
- 例外：`Suspicious Stew` → `谜之炖菜`。

### 珊瑚

- `Dead <... Coral>` 一律带“的”，译作 `失活的<...珊瑚>`。

### 加工与状态前缀

- `Stripped`（`去皮…`）、`Polished`（`磨制…`）、`Cracked`（`裂纹…`）、`Cut`（`切制…`）、`Smooth`（`平滑…`）、`Infested`（`虫蚀…`）、`Chiseled`（`雕纹…`）均不带“的”。
- 例外：`Mossy Cobblestone` 整体译作 `苔石`（衍生 `苔石台阶/楼梯/墙`）。

### 粗金属与生熟食物

- `Raw <金属>` 译作 `粗<金属>`，不加“的”，如 `Raw Iron` → `粗铁`。
- `Raw <肉/鱼>` 译作 `生…`，`Cooked <肉/鱼>` 译作 `熟…`，均不加“的”，如 `Raw Cod` → `生鳕鱼`、`Cooked Chicken` → `熟鸡肉`。

### 颜色前缀

- 常规方块与物品保留“色”，作 `<颜色>色<X>`，如 `White Stained Glass` → `白色染色玻璃`、`Black Harness` → `黑色挽具`。
- 例外去“色”：`Blue Ice` → `蓝冰`、`Blue Orchid` → `兰花`、`Red Sand` → `红沙`、`Red Sandstone` 系列 → `红砂岩…`、`Red Shrub` → `红灌木`。

### 工具与武器

- `Wooden` 译作单字 `木`，如 `Wooden Pickaxe` → `木镐`。
- `Stone` 减字为 `石`，如 `Stone Sword` → `石剑`、`Stone Spear` → `石矛`。
- `Golden` 译作单字 `金`，如 `Golden Sword` → `金剑`（`Golden Apple`、`Golden Boots` 等 `Gold`/`Golden` 物品同规）。
- 其余材质直拼，如 `铁镐`、`铜斧`、`钻石剑`、`下界合金锄`。

### 盔甲与挽具

- 玩家装备、纹饰与常规语境用 `盔甲`，如 `Armor Stand` → `盔甲架`。
- 坐骑与动物护甲用 `…铠`，如 `Horse Armor` → `马铠`、`Wolf Armor` → `狼铠`、`Nautilus Armor` → `鹦鹉螺铠`。
- `Harness` 译作 `挽具`。

### 装备槽位提示

- 身体与头部按动词区分：`When on Chest:` → `穿在身上时：`，`When on Legs/Feet:` → `穿在腿上/脚上时：`，`When on Head:` → `戴在头上时：`。
- 手部按持握区分：`When in Main/Off Hand:` → `在主/副手时：`，`When held:` → `手持时：`。
- 通用穿戴：`When equipped:` → `装备时：`，`When worn:` → `穿戴时：`，`When saddled:` → `装备鞍时：`。

### 石头与深板岩

- 独立方块 `Stone` 及其常规变体用 `石头`，如 `Stone Slab` → `石头台阶`、`Smooth Stone` → `平滑石头`。
- 复合砖石中的 `Stone` 减字为 `石`，如 `Stone Bricks` → `石砖`、`End Stone` → `末地石`。
- `Deepslate` 作矿石定语（`Deepslate ... Ore`）译作 `深层`，其余方块与制品一律译作 `深板岩`。

### 砖与砖块

- 独立红砖物品 `Brick` → `红砖`，方块 `Bricks` → `红砖块`（衍生 `红砖台阶/楼梯/墙`）。
- 复合词定语 `Brick` 统一译作 `砖`，如 `Deepslate Brick Slab` → `深板岩砖台阶`。
- 复数 `Bricks` 若存在同名单片砖物品或其变体则译作 `砖块`，如 `Nether Bricks` → `下界砖块`、`Red Nether Bricks` → `红色下界砖块`、`Resin Bricks` → `树脂砖块`。
- 其余复数 `Bricks` 一律译作 `砖`，如 `Stone Bricks` → `石砖`、`Sulfur Bricks` → `硫黄砖`。

### 单字树名

- 适用树种：`Oak`（橡）、`Dark Oak`（深色橡）、`Pale Oak`（苍白橡）、`Poplar`（杨）。
- 树叶与树苗补“树”，作 `<X>树树叶`、`<X>树树苗`，如 `Oak Leaves` → `橡树树叶`。
- 原木、木板、木材与制品补“木”，作 `<X>木原木`、`<X>木木板`、`<X>木<制品>`，如 `Oak Planks` → `橡木木板`、`Poplar Shelf` → `杨木展示架`。
- `<Tree> Wood` 译作 `<X>木`，如 `Poplar Wood` → `杨木`。

### 多字树名

- 适用树种：`Spruce`（云杉）、`Birch`（白桦）、`Jungle`（丛林）、`Acacia`（金合欢）、`Cherry`（樱花）、`Mangrove`（红树）、`Crimson`（绯红）、`Warped`（诡异）。
- 自带部位或材质语素的专属部件（`Leaves`/`Sapling`/`Log`/`Planks`/`Propagule`/`Roots`/`Stem`/`Hyphae`）直拼基础名，如 `云杉树叶`、`红树根`、`绯红菌柄`。
- `Wood` 及门、船、台阶、栅栏、展示架等通用制品在基础名后加“木”，如 `云杉木`、`金合欢木船`。

### 竹

- 独立物品与盆栽用 `竹子`（`竹子`、`竹子盆栽`）。
- 制品前缀统一减为单字 `竹`，如 `竹块`、`竹门`、`竹筏`。
- 例外：`Bamboo Planks` → `竹板`、`Bamboo Shoot` → `竹笋`。

### 悬挂式告示牌

- `<Tree> Hanging Sign` 将 `悬挂式` 前置，作 `悬挂式<X>木告示牌`，竹类作 `悬挂式竹告示牌`。

### 材料块与容器方块

- 材料块 `Block of <X>` 倒装并省去“之/的”，作 `<X>块`，如 `Block of Raw Iron` → `粗铁块`。
- 装填炼药锅 `<物质> Cauldron` 译作 `装有<物质>的炼药锅`，如 `Water Cauldron` → `装有水的炼药锅`。
- 盆栽 `Potted <Plant>` 译作 `<植物>盆栽`，不加“盆栽的”，如 `Potted Allium` → `绒球葱盆栽`。
- 蜡烛蛋糕 `Cake with (<Color>) Candle` 译作 `插上(<颜色>)蜡烛的蛋糕`。

### 墙上附着方块

- key 含 `wall_sign`、`wall_hanging_sign`、`wall_torch`、`wall_fan`、`wall_head`、`wall_skull` 时统一前置 `墙上的`，如 `Wall Torch` → `墙上的火把`。
- 珊瑚扇同时叠加“失活”与“墙上”时省去内层“的”，如 `Dead Brain Coral Wall Fan` → `墙上的失活脑纹珊瑚扇`。
- 末尾为 `Wall` 的独立石墙/砖墙方块译作 `<X>墙`，如 `Andesite Wall` → `安山岩墙`。

### 生物与玩家头颅

- `Skeleton/Wither Skeleton Skull` 译作 `<生物>头颅`，`Dragon Head` 译作 `龙首`。
- `Creeper/Piglin/Player/Zombie Head` 译作 `<生物>的头`（`%s's Head` → `%s的头`）。
- 挂墙时前置 `墙上的` 且保留内层“的”，如 `Creeper Wall Head` → `墙上的苦力怕的头`。
- 例外：`Piston Head` → `活塞头`。

### 桶

- 空桶 `Bucket` 译作 `铁桶`，装填液体、粉雪或生物的复合桶统一用 `<X>桶`，如 `Water Bucket` → `水桶`、`Bucket of Axolotl` → `美西螈桶`。
- `Milk` 译作 `奶`（不译出来源，因为牛、山羊均可产奶），`Milk Bucket` → `奶桶`。

### 运输与载体

- 带箱船将 `运输` 嵌入木种与 `船` 之间，作 `<木种>运输船`（无木种作 `运输船`），如 `Oak Boat with Chest` → `橡木运输船`。
- 运输矿车与竹筏前置 `运输`：`Minecart with Chest` → `运输矿车`、`Bamboo Raft with Chest` → `运输竹筏`。
- 其余载物矿车作 `<载物>矿车`，如 `Minecart with TNT` → `TNT矿车`。
- 例外：`Minecart with Furnace` → `动力矿车`。

### 刷怪蛋

- `<Mob> Spawn Egg` 统一译作 `<生物>刷怪蛋`。

## 旗帜图案
<!-- @scope {"id": "scope.banner", "include": ["block.minecraft.banner.*", "item.minecraft.*_banner_pattern", "item.minecraft.*_banner_pattern.*"]} -->

### 去“色”嵌槽格局

- `<C>` 为去“色”颜色名，单双字色同规（如 `黑`、`淡蓝`）。
- 满底：`Fully <C> Field` → `<C>底`。
- 横条：`Base` → `底<C>横条`、`Fess` → `中<C>横条`、`Chief` → `顶<C>横条`。
- 竖条：`Pale` → `中<C>竖条`、`Pale Dexter` → `右<C>竖条`、`Pale Sinister` → `左<C>竖条`。
- 斜条：`Bend` → `右<C>斜条`、`Bend Sinister` → `左<C>斜条`。
- 方角：`Base Dexter/Sinister Canton` → `右/左底<C>方`、`Chief Dexter/Sinister Canton` → `右/左顶<C>方`。
- 三角：`Chevron` → `底<C>三角`、`Inverted Chevron` → `顶<C>三角`。
- 十字与条纹：`Cross` → `<C>正十字`、`Saltire` → `<C>斜十字`、`Paly` → `<C>竖条纹`。

### 常规格局与图案物品

- 其余格局一律保留“色”，作 `<颜色>色<图案>`，如 `White Bordure` → `白色方框边`、`White Thing` → `白色Mojang徽标`。
- 旗帜图案物品泛称 `Banner Pattern` → `旗帜图案`，带名 `<Pattern> Banner Pattern` → `<图案>旗帜图案`。
- `.desc` 仅写 `<图案>`。

## 陶片与盔甲纹饰
<!-- @scope {"id": "scope.pottery_trim", "include": ["item.minecraft.*_pottery_sherd", "item.minecraft.*_pottery_shard", "item.minecraft.pottery_shard_*", "item.minecraft.*_smithing_template", "item.minecraft.*_smithing_template.*", "item.minecraft.smithing_template", "item.minecraft.smithing_template.*", "trim_pattern.*", "trim_material.*"]} -->

- 纹样陶片作 `<纹样>纹样陶片`。
- 锻造模板泛称 `锻造模板`，带纹样 `<Pattern> Armor Trim` 作 `<纹样>盔甲纹饰`。
- 纹饰材料 `<X> Material` 作 `<X>质`，如 `Amethyst Material` → `紫水晶质`。

## 药水与药箭
<!-- @scope {"id": "scope.potion", "include": ["item.minecraft.potion.effect.*", "item.minecraft.splash_potion.effect.*", "item.minecraft.lingering_potion.effect.*", "item.minecraft.tipped_arrow.effect.*"]} -->

### 常规构词

- `Potion of <Effect>` 译作 `<效果>药水`，喷溅型与滞留型分别前置 `喷溅型`、`滞留型`。
- 药箭 `Arrow of <Effect>` 译作 `<效果>之箭`。

### 与状态效果异名的药水

- `Infestation` → `虫蚀`（效果 `Infested` 为 `寄生`）。
- `Poison` → `剧毒`（效果为 `中毒`）。
- `Regeneration` → `再生`（效果为 `生命恢复`）。
- `Slowness` → `迟缓`（效果为 `缓慢`）。
- `Water Breathing` → `水肺`（效果为 `水下呼吸`）。
- `the Turtle Master` → `神龟`。

### 基础与不可合成系列

- `Water Bottle` → `水瓶`（`喷溅型/滞留型水瓶`），`Arrow of Splashing` → `喷溅之箭`。
- `Awkward`/`Mundane`/`Thick` 分别作 `粗制的`/`平凡的`/`浓稠的药水`（喷溅/滞留型直接前置），对应药箭均作 `药箭`。
- `Uncraftable` 系列前置 `不可合成的`，作 `不可合成的药水`、`不可合成的药箭`、`不可合成的喷溅型药水`、`不可合成的滞留型药水`。

## 地图
<!-- @scope {"id": "scope.filled_map", "include": ["filled_map.*", "item.minecraft.*_map"]} -->

### 地图命名

- `<Location> Explorer Map` 译作 `<地点>探险家地图`。
- `Buried <地点> Map` 译作 `埋藏的<地点>地图`（例外：`Buried Treasure Map` → `藏宝图`）。
- 其余结构与营地地图译作 `<地点>地图`。

### 缩放与编号

- `Scaling at 1:%s` → `比例尺1:%s`。
- `(Level %s/%s)` → `（缩放等级%s/%s）`。
- `ID #%s` → `ID #%s`。

## 生物群系
<!-- @scope {"id": "scope.biome", "include": ["biome.minecraft.*"]} -->

- `Birch Forest` 省“白”作 `桦木森林`，`Old Growth Birch Forest` → `原始桦木森林`。
- `Old Growth Pine Taiga` → `原始松木针叶林`，`Mangrove Swamp` → `红树林沼泽`。
- `Bamboo Jungle` → `竹林`，`Cherry Grove` → `樱花树林`（对照 `Grove` → `雪林`）。

## 实体属性
<!-- @scope {"id": "scope.attribute", "include": ["attribute.name.*"]} -->

- `Armor` → `护甲值`，`Armor Toughness` 仍作 `盔甲韧性`。
- `Luck` → `幸运值`（状态效果为 `幸运`）。
- `Speed` → `速度`（状态效果为 `迅捷`）。

## 魔咒
<!-- @scope {"id": "scope.enchantment", "include": ["enchantment.minecraft.*"]} -->

- `Curse of <X>` 倒装译作 `<X>诅咒`，如 `Curse of Binding` → `绑定诅咒`。

## 音画作品
<!-- @scope {"id": "scope.media", "include": ["item.minecraft.music_disc_*.desc", "item.minecraft.disc_fragment_*.desc", "jukebox_song.*", "music.*", "painting.minecraft.*.title", "painting.minecraft.*.author"]} -->

### 音乐与唱片

- 曲名与作者保留原文，例外：`Kumi Tanioka` 在 `music.game.*` 中译作 `谷冈久美`。
- 曲名后的版本或乐器括注译出并改用全角括号，如 `Lena Raine - Creator (Music Box)` → `Lena Raine - Creator（八音盒）`。
- 唱片残片描述 `Music Disc - 5` 译作 `音乐唱片 - 5`。

### 画作

- 画作标题与作者保留原语言原文。

## 音效字幕
<!-- @scope {"id": "scope.subtitles", "include": ["subtitles.*"]} -->

### 有主体音效

- 作 `<发声主体>：<动作或声音>`。
- 按中文自然动作调整语序或意译交互，如 `Bee leaves hive` → `蜜蜂：离巢`、`Lever clicks` → `拉杆：拉动`。

### 无主体环境音

- 直接作名词或动宾短语，如 `Eerie noise` → `怪异的噪声`、`Splashing` → `溅起水花`。

## 统计项
<!-- @scope {"id": "scope.stat", "include": ["stat.*"]} -->

- 次数类收尾用 `…次数`，如 `Animals Bred` → `繁殖动物次数`。
- 距离类收尾用 `…距离`，如 `Distance by Boat` → `坐船移动距离`（例外：`Distance Fallen` → `摔落高度`）。
- 数量与伤害量分别用 `…数` 与 `…量`，如 `Fish Caught` → `捕鱼数`、`Damage Dealt` → `造成伤害量`。
- 时长与间隔作 `…时长`、`…时间` 或 `自上次…`，如 `Time Played` → `游戏时长`、`Time Since Last Death` → `自上次死亡`。

## 死亡消息
<!-- @scope {"id": "scope.death", "include": ["death.*"]} -->

- 保持紧凑陈述句，句末不加句号，如 `%1$s was shot by %2$s` → `%1$s被%2$s射杀`。
- 英文后置的战斗/逃离状语提前：`while fighting %2$s` → `%1$s在与%2$s战斗时…`、`while trying to escape %2$s` → `%1$s在试图逃离%2$s时…`。
- 状语带 `wielding %3$s` 时作 `持有%3$s的%2$s`。
- 带武器 `using/with %3$s` 嵌作 `被%2$s用%3$s…`，如 `%1$s was slain by %2$s using %3$s` → `%1$s被%2$s用%3$s杀死了`。

## 命令与参数反馈
<!-- @scope {"id": "scope.commands", "include": ["commands.*", "argument.*", "parsing.*"]} -->

### 标点与无变化提示

- 反馈与报错句末不加句号。
- 含多句时仅在句间用全角句号 `。`，如 `测试失败。计数：%s`。
- `Nothing changed. ...` 固定起手 `无变化，……`（英文句号改中文逗号），如 `无变化，该玩家已是管理员`。
- 目标已处于预期状态时多用 `原已`，如 `白名单原已开启`、`游戏规则%s原已设为%s`。

### 解析与校验报错

- `Expected X: got/was/found Y` 固定作 `应为……：实际为……`，如 `Expected a list: got %s` → `应为列表：实际为%s`。
- 未闭合括号或引号固定作 `……不成对`，如 `选项的方括号不成对`、`字符串引号不成对`。

### 版本信息

- `commands.version.*` 整组保留英文原文，如 `Server version info:`、`build_time = %s`、`stable = yes`。

## 进度
<!-- @scope {"id": "scope.advancements", "include": ["advancements.*"]} -->

- 标题偏四字或简练名词性短语。
- 描述多用无主语祈使短语，单句陈述句末不加句号。
- 问句、感叹句、省略号及含 `\n注：` 的多行附注保留对应标点。

## 游戏规则与设置选项
<!-- @scope {"id": "scope.options_gamerule", "include": ["gamerule.*", "options.*"]} -->

### 游戏规则

- `gamerule` 规则名不加句号。
- `.description` 完整说明句末一律加 `。`。

### 设置选项

- `options.*` 键值展示作 `<项>：<值>`，如 `聊天延迟：%s秒`。
- 完整句 `.tooltip` / `.description` 句末加 `。`，短标签提示（如 `辅助功能设置`）不加。

## 键盘按键
<!-- @scope {"id": "scope.keyboard", "include": ["key.keyboard.*"]} -->

### 保留英文原文

- 常用控制键、修饰键与功能键保留英文原文，如 `Backspace`、`Caps Lock`、`Enter`、`Tab`、`F1`–`F25` 等。

### 简写、修饰键与方向键

- `Escape` 简写为 `Esc`。
- `Control` 作按键名统一简写为 `Ctrl`，仅在 macOS 专属提示等原文作 `Control` 时保留 `Control`。
- 左右修饰键前置 `左`/`右` 不留空格，如 `Left Control` → `左Ctrl`。
- 方向键作 `上/下/左/右方向键`，`Space` 作 `空格`。

### 编号与前缀键

- 前缀后留半角空格：`AC <动作>`、`小键盘 <X>`、`国际键 <N>`、`语言键 <N>`。
