# 我的世界原版翻译风格规范

本文件约定术语表之外的按域构词体例、整类不译规则与全局格式。具体词条与基础名词查 `Vanilla/terms/` 下的术语表。

## 1. 方块、物品与实体
<!-- @scope {"id": "scope.block_item", "include": ["block.minecraft.*", "item.minecraft.*", "entity.minecraft.*"]} -->

适用范围：方块、物品与常规实体名称。

### 1.1 修饰词与助词「的」

- 深板岩与深层
  - `Deepslate` 用作矿石定语（`Deepslate ... Ore`）时译作 `深层`，例如 `Deepslate Diamond Ore` 译作 `深层钻石矿石`。
  - 英文出现几次 `Deepslate` 矿石，对应译文就出现几次 `深层`。
  - 其余普通方块、工具或制品一律译作 `深板岩`，例如 `Deepslate Bricks` 译作 `深板岩砖`。
- 氧化铜系列与涂蜡嵌套
  - `Exposed`（斑驳）、`Weathered`（锈蚀）、`Oxidized`（氧化）直接修饰铜制品时必须带「的」，写作 `斑驳的…`、`锈蚀的…`、`氧化的…`。
  - 外层叠加 `Waxed`（涂蜡）时，`涂蜡` 可以带「的」也可以省略，例如 `Waxed Copper Block` 译作 `涂蜡铜块`；内层氧化度一般保留「的」，例如 `Waxed Exposed Copper` 译作 `涂蜡的斑驳铜块`。
- 可疑的
  - `Suspicious <方块>` 译作 `可疑的<方块>`，必须保留「的」，例如 `Suspicious Sand` 译作 `可疑的沙子`。
  - `Suspicious Stew` 为例外，译作 `谜之炖菜`。
- 粗金属与失活珊瑚
  - `raw_iron`、`raw_gold`、`raw_copper` 系列的 `Raw <Metal>` 译作 `粗<金属>`，不加「的」，例如 `Raw Iron` 译作 `粗铁`。
  - `Dead <... Coral>` 一律译作 `失活的<...珊瑚>`，保留「的」。
- 固定不加「的」的加工与材质前缀
  - `Stripped`（`去皮…`）、`Polished`（`磨制…`）、`Cracked`（`裂纹…`）、`Cut`（`切制…`）、`Smooth`（`平滑…`）、`Infested`（`虫蚀…`）、`Waxed`（`涂蜡…`）。
  - `Chiseled` 译作 `雕纹…`；1.19.2 及更早版本写作 `錾制…`。
  - `Mossy` 译作 `苔…`，例如 `Mossy Cobblestone` 译作 `苔石`。

### 1.2 树木、木材与竹子

`terms-v1.tsv` 只收基础树种（多字树名收基础名，单字树根收 `X木|X树`），具体构词按三类处理：

- 单字树根（`Oak` 橡、`Dark Oak` 深色橡、`Pale Oak` 苍白橡、`Poplar` 杨）
  - 核心词根只有一字，必须补成双音节。
  - 树叶与树苗在词根后加「树」，写作 `<X>树树叶`、`<X>树树苗`，例如 `Oak Leaves` 译作 `橡树树叶`、`Dark Oak Sapling` 译作 `深色橡树树苗`。
  - 原木、木板、木材与木制品在词根后加「木」，写作 `<X>木原木`、`<X>木木板`、`<X>木<制品>`，例如 `Oak Planks` 译作 `橡木木板`。
  - `<Tree> Wood` 本身译作 `<X>木`，例如 `Oak Wood` 译作 `橡木`、`Pale Oak Wood` 译作 `苍白橡木`、`Poplar Wood` 译作 `杨木`。
- 多字树名（`Spruce` 云杉、`Birch` 白桦、`Jungle` 丛林、`Acacia` 金合欢、`Cherry` 樱花、`Mangrove` 红树、`Crimson` 绯红、`Warped` 诡异）
  - 专属部件 `Leaves`（树叶）、`Sapling`（树苗）、`Log`（原木）、`Planks`（木板）、`Propagule`（胎生苗）、`Roots`（根）、`Stem`（菌柄）、`Hyphae`（菌核）自带材质或部位词素，直接拼在基础名后，例如 `云杉树叶`、`云杉原木`、`云杉木板`、`红树树叶`、`红树原木`、`红树木板`、`红树根`、`绯红菌柄`、`诡异菌核`。
  - 木材（`<Tree> Wood`）及门、船、台阶、栅栏等通用制品不自带材质语素，在基础名后加「木」，写作 `<X>木` 或 `<X>木<制品>`，例如 `云杉木`、`金合欢木船`、`白桦木台阶`、`红树木`、`红树木船`、`诡异木活板门`。
- 竹（`Bamboo`，非木材）
  - 独立物品与盆栽译作 `竹子` 和 `竹子盆栽`。
  - 竹制品前缀一律减为单字 `竹`，例如 `竹块`、`竹门`、`竹台阶`、`竹筏`、`竹马赛克`。
  - `Bamboo Planks` 减字译作 `竹板`。

### 1.3 高歧义通名（砖、石、桶、盔甲）

下列名词在独立物品与复合词之间会增减字或切换用词，不能只靠术语表硬匹配：

- 砖与砖块（`Brick` / `Bricks`）
  - 独立红砖物品 `Brick` 译作 `红砖`，方块 `Bricks` 译作 `红砖块`，成套衍生方块 `Brick Slab/Stairs/Wall` 译作 `红砖台阶/楼梯/墙`。
  - 作复合词定语时，`Brick` 统一译作 `砖`，例如 `Nether Brick` 译作 `下界砖`、`Resin Brick` 译作 `树脂砖`、`Deepslate Brick Slab` 译作 `深板岩砖台阶`。
  - 复数 `Bricks` 存在同名单片砖物品时译作 `砖块`，例如 `Nether Bricks` 译作 `下界砖块`、`Resin Bricks` 译作 `树脂砖块`、`Red Nether Bricks` 译作 `红色下界砖块`。
  - 复数 `Bricks` 不存在同名单片砖物品时统一译作 `砖`，例如 `Stone Bricks` 译作 `石砖`、`Deepslate Bricks` 译作 `深板岩砖`、`Mud Bricks` 译作 `泥砖`、`Tuff Bricks` 译作 `凝灰岩砖`、`Prismarine Bricks` 译作 `海晶石砖`、`Quartz Bricks` 译作 `石英砖`。
- 石头与石质（`Stone`）
  - 独立方块 `Stone`、平滑变体与石制常规方块（`Stone Slab/Stairs/Button/Pressure Plate`、`Smooth Stone`、`Infested Stone`）用 `石头`。
  - 石质工具武器（`Stone Sword/Pickaxe/Axe/Shovel/Hoe/Spear` 译作 `石剑/石镐/石斧/石锹/石锄/石矛`）及复合砖石词素（`Stone Bricks` 译作 `石砖`、`End Stone` 译作 `末地石`）减字为 `石`。
- 桶（`Bucket`）
  - 空桶独立物品 `Bucket` 译作 `铁桶`。
  - 装填物或生物的复合桶统一用 `桶`，例如 `Water Bucket` 译作 `水桶`、`Lava Bucket` 译作 `熔岩桶`、`Powder Snow Bucket` 译作 `细雪桶`、`Bucket of Axolotl` 译作 `美西螈桶`。
  - `Milk` 本义写 `奶`，不写 `牛奶`，因此 `Milk Bucket` 译作 `奶桶`。
- 盔甲与护甲（`Armor`）
  - 穿戴装备、纹饰与常规语境用 `盔甲`，例如 `Armor Stand` 译作 `盔甲架`。
  - 坐骑护甲用 `…铠`，例如 `Horse Armor` 译作 `马铠`、`Nautilus Armor` 译作 `鹦鹉螺铠`。

### 1.4 附着、容器、载体与药水

- 墙上附着方块
  - key 含 `wall_sign`、`wall_hanging_sign`、`wall_banner`、`wall_torch`、`wall_fan`、`wall_skull`、`wall_head` 时，`Wall <X>` 一律译作 `墙上的<X>`，例如 `Wall Torch` 译作 `墙上的火把`、`Acacia Wall Sign` 译作 `墙上的金合欢木告示牌`。
  - 末尾为 `Wall` 的独立方块（`<X> Wall`）是石墙或砖墙，译作 `<X>墙`，例如 `Andesite Wall` 译作 `安山岩墙`。
- 盆栽
  - `potted_*` 对应的 `Potted <Plant>` 译作 `<植物>盆栽`，不用 `盆栽的…`，例如 `Potted Allium` 译作 `绒球葱盆栽`。
- 刷怪蛋
  - `*_spawn_egg` 对应的 `<Mob> Spawn Egg` 统一译作 `<生物>刷怪蛋`。
- 运输与载体
  - `<X> with Chest` 按载体惯例译作 `运输<X>`，例如 `Minecart with Chest` 译作 `运输矿车`、`Oak Boat with Chest` 译作 `橡木运输船`、`Bamboo Raft with Chest` 译作 `运输竹筏`。
  - 其余载人或装物矿车译作 `<X>矿车`，例如 `Minecart with TNT` 译作 `TNT矿车`、`Minecart with Hopper` 译作 `漏斗矿车`。
- 药水与药箭
  - 普通药水 `Potion of <Effect>` 译作 `<效果>药水`；喷溅型加前缀 `喷溅型`，写作 `喷溅型<效果>药水`；滞留型加前缀 `滞留型`，写作 `滞留型<效果>药水`。
  - 药箭 `Arrow of <Effect>` 译作 `<效果>之箭`。
  - 基础未合成药水与药箭除外，固定译作 `粗制的药水`、`不可合成的药水`、`药箭`、`不可合成的药箭`。

## 2. 特殊制品域

### 2.1 旗帜图案
<!-- @scope {"id": "scope.banner", "include": ["block.minecraft.banner.*", "item.minecraft.*_banner_pattern"]} -->

适用范围：旗帜图案层与旗帜图案物品。

- 颜色嵌槽总则
  - 16 种颜色在下列去「色」格局以及 `Cross`（正十字）、`Saltire`（斜十字）、`Paly`（竖条纹）中一律省去「色」字，无论单字色（`黑`、`白`、`红`）还是双字色（`淡蓝`、`淡灰`、`黄绿`、`品红`、`粉红`）。
  - 其余独立格局一律采用 `<颜色>色<图案>` 前置。
- 去「色」嵌槽与固定格局（`<C>` 为去「色」后的颜色名，如 `黑`、`淡蓝`）
  - 满底：`Fully <C> Field` 译作 `<C>底`。
  - 横条：`Base` 译作 `底<C>横条`、`Fess` 译作 `中<C>横条`、`Chief` 译作 `顶<C>横条`。
  - 竖条：`Pale` 译作 `中<C>竖条`、`Pale Dexter` 译作 `右<C>竖条`、`Pale Sinister` 译作 `左<C>竖条`。
  - 斜条：`Bend` 译作 `右<C>斜条`、`Bend Sinister` 译作 `左<C>斜条`。
  - 方角：`Base Dexter Canton` 译作 `右底<C>方`、`Base Sinister Canton` 译作 `左底<C>方`、`Chief Dexter Canton` 译作 `右顶<C>方`、`Chief Sinister Canton` 译作 `左顶<C>方`。
  - 三角：`Chevron` 译作 `底<C>三角`、`Inverted Chevron` 译作 `顶<C>三角`。
  - 十字与条纹：`Cross` 译作 `<C>正十字`、`Saltire` 译作 `<C>斜十字`、`Paly` 译作 `<C>竖条纹`。
- 保留 `<颜色>色` 前置的格局
  - 边框与波纹：`Bordure`（方框边）、`Bordure Indented`（波纹边）、`Base Indented`（底波纹）、`Chief Indented`（顶波纹）。
  - 几何与渐淡：`Field Masoned`（砖纹）、`Roundel`（圆形）、`Lozenge`（菱形）、`Gradient`（自上渐淡）、`Base Gradient`（自下渐淡）。
  - 对半与斜分：`Per Fess`（上半方形）、`Per Fess Inverted`（下半方形）、`Per Pale`（右半方形）、`Per Pale Inverted`（左半方形）、`Per Bend`（左上三角）、`Per Bend Sinister`（右上三角）、`Per Bend Inverted`（右下三角）、`Per Bend Sinister Inverted`（左下三角）。
  - 徽章图案：`Creeper Charge`（苦力怕盾徽）、`Flower Charge`（花朵盾徽）、`Skull Charge`（头颅盾徽）、`Thing`（`Mojang徽标`）、`Snout`（猪鼻）、`Globe`（地球）、`Flow`（涡流）、`Guster`（旋风）。
- 旗帜图案物品
  - `<Pattern> Banner Pattern` 译作 `<图案>旗帜图案`，例如 `Field Masoned Banner Pattern` 译作 `砖纹旗帜图案`。

### 2.2 陶片与盔甲纹饰
<!-- @scope {"id": "scope.pottery_trim", "include": ["item.minecraft.*_pottery_sherd", "item.minecraft.*_armor_trim_smithing_template", "trim_pattern.*", "trim_material.*"]} -->

适用范围：纹样陶片、锻造模板盔甲纹饰与纹饰材料。

- 陶片物品统一译作 `<纹样>纹样陶片`。
- 盔甲纹饰统一译作 `<纹样>盔甲纹饰`；盔甲纹饰材料 `<X> Material` 统一译作 `<X>质`，例如 `Amethyst Material` 译作 `紫水晶质`。
- 两类纹样原型各自查对应 `special/` 分表：例如 `Flow` 在陶片与旗帜中为 `涡流`；`Explorer` 在陶片中为 `探险`，在探险家地图中为 `探险家`。

## 3. 域外特例

### 3.1 生物群系
<!-- @scope {"id": "scope.biome", "include": ["biome.minecraft.*"]} -->

适用范围：生物群系名称中脱离木材常规构词的特例。

- `Birch Forest` 省「白」，译作 `桦木森林`。
- `Old Growth Pine Taiga` 译作 `原始松木针叶林`。
- `Mangrove Swamp` 译作 `红树林沼泽`。

### 3.2 属性
<!-- @scope {"id": "scope.attribute", "include": ["attribute.name.*"]} -->

适用范围：属性名称中脱离物品常规用词的特例。

- `attribute.name.armor` 译作 `护甲值`。
- `attribute.name.armor_toughness` 译作 `盔甲韧性`。

## 4. 唱片、音乐与画作
<!-- @scope {"id": "scope.media", "include": ["item.minecraft.music_disc_*.desc", "jukebox_song.*", "music.*", "painting.minecraft.*.title", "painting.minecraft.*.author"]} -->

适用范围：音乐唱片曲名、曲目作者以及画作标题与作者。

- 音乐唱片曲名与曲目作者保留英文原文，不音译也不意译，例如 `C418 - cat`、`Lena Raine - Creator`、`Hyper Potions - Lava Chicken`。
- 曲名后的版本或乐器括注按中文惯例译出，并使用全角括号，例如 `Lena Raine - Creator (Music Box)` 译作 `Lena Raine - Creator（八音盒）`。
- 画作标题与作者保留英文或原语言原文，例如 `Albanian`、`de_aztec`、`Kristoffer Zetterstrand`。

## 5. 功能文本

### 5.1 字幕
<!-- @scope {"id": "scope.subtitles", "include": ["subtitles.*"]} -->

适用范围：游戏内辅助功能声音字幕。

- 有明确发声主体时，统一写作 `<发声主体>：<动作或声音>`，中间用全角冒号 `：` 且不留空格，例如 `Amethyst chimes` 译作 `紫水晶：叮铃`。
- 英文存在动词歧义或需要调整主谓语序时，按中文自然动作译出，例如 `Bee leaves hive` 译作 `蜜蜂：离巢`、`Goat Horn breaks off` 译作 `山羊：断角`、`Fireball whooshes` 译作 `火焰弹：呼啸`。
- 交互类字幕按实际交互语义意译，例如 `Lever clicks` 译作 `拉杆：拉动`。
- 没有明确发声主体的环境音效或通用音效，直接写名词或动作，例如 `Eerie noise` 译作 `怪异的噪声`、`Splashing` 译作 `溅起水花`。

### 5.2 统计项
<!-- @scope {"id": "scope.stat", "include": ["stat.*"]} -->

适用范围：游戏内统计页面条目。

- 次数类统计收尾用 `…次数`，例如 `Animals Bred` 译作 `繁殖动物次数`。
- 距离类统计收尾用 `…距离`，例如 `Distance by Boat` 译作 `坐船移动距离`。

### 5.3 死亡消息
<!-- @scope {"id": "scope.death", "include": ["death.*"]} -->

适用范围：玩家与实体死亡提示文本。

- 保持紧凑陈述句，句末不加句号，例如 `%1$s was shot by %2$s` 译作 `%1$s被%2$s射杀`。

### 5.4 进度
<!-- @scope {"id": "scope.advancements", "include": ["advancements.*"]} -->

适用范围：游戏内进度标题与描述文本。

- 标题偏四字或简练名词性短语。
- 描述多用无主语祈使短语，句末不加句号，例如 `Discover every biome` 译作 `发现所有的生物群系`。

## 6. 全局策略
<!-- @scope {"id": "global", "apply": "always"} -->

适用范围：全部文本。

### 6.1 查表与体例分工

- 本文件记录依赖语境删字、改序、嵌槽、加减「的」及整类不译的规则。
- 具体单个不译词（如 `TNT`）与基础名词留在 `terms-v1.tsv`；各专属域与跨表同形词的词条译名留在对应域分表或 `special/` 分表，体例写法遵循本文件对应章节。

### 6.2 全局不译与专名

- 品牌与产品专名：`Minecraft`、`Minecraft Realms`、`Realms`、`Mojang` 保留英文原文，不作音译或意译；旗帜图案中的 `Mojang徽标` 按官方中文写法保留 `Mojang`。
- 罗马数字等级：附魔等级（`enchantment.level.*`）与药水等级（`potion.potency.*`）统一保留罗马数字 `I`、`II`、`III`、`IV` 等，不改为阿拉伯数字或中文数字。

### 6.3 标点与间距

- 中西文与占位符间距：中文与英文缩写、数字及 `%s`、`%1$s` 等格式化占位符之间不加空格，例如 `TNT爆炸已禁用`、`%1$s被%2$s射杀`、`自定义Boss栏%s现为可见`。
- 英文署名例外：极少数保留英文书名或署名格式的内容按英文空格习惯处理，例如 `%1$s 著`。
- 全角标点：说明性冒号、括号、引号统一用全角（`：`、`（）`、`“”`）；命令或语法示例中的符号保持半角，例如 `'/perf stop'`。
