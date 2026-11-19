# 我的世界原版翻译风格规范

本文件替代原 `qa-rules.tsv`，用自然语言约定术语表之外的构词体例、高歧义通名用法、整类不译规则与排版格式。具体单个不译词（如 `TNT`）与基础名词留在 `terms-v1.tsv`；依赖语境删字、改序、嵌槽或整类不译的规则写在本文件。

## 1. 整类不译规则

- **音乐唱片曲名与曲目作者**：`music_disc_*.desc`、`jukebox_song.*`、`music.*` 中的曲名与作者名保留英文原文，不作音译或意译（如 `C418 - cat`、`Lena Raine - Creator`、`Hyper Potions - Lava Chicken`）。曲名后的版本或乐器括注按中文惯例译出并使用全角括号，如 `Lena Raine - Creator (Music Box)` 译作 `Lena Raine - Creator（八音盒）`。
- **画作标题与作者**：`painting.minecraft.*.title` 与 `.author` 保留英文或原语言原文（如 `Albanian`、`de_aztec`、`Kristoffer Zetterstrand`）。
- **罗马数字等级**：附魔等级与药水等级（`enchantment.level.*`、`potion.potency.*`）统一保留罗马数字 `I`、`II`、`III`、`IV` 等。
- **品牌与产品专名**：`Minecraft`、`Minecraft Realms`、`Realms`、`Mojang` 保留英文；旗帜图案里的 `Mojang徽标` 按官方中文写法保留 `Mojang`。

## 2. 修饰词与助词「的」

- **深板岩与深层**：`Deepslate` 用作矿石定语（`Deepslate ... Ore`）时译作 `深层`（如 `Deepslate Diamond Ore` → `深层钻石矿石`），且英文出现几次 `Deepslate` 矿石对应译文就应出现几次 `深层`；其余普通方块、工具或制品一律译作 `深板岩`（如 `Deepslate Bricks` → `深板岩砖`）。
- **氧化铜系列与涂蜡嵌套**：`Exposed`（斑驳）、`Weathered`（锈蚀）、`Oxidized`（氧化）直接修饰铜制品时须带「的」，即 `斑驳的…`、`锈蚀的…`、`氧化的…`。外层叠加 `Waxed`（涂蜡）时，`涂蜡` 可带也可省略「的」（如 `Waxed Copper Block` → `涂蜡铜块`），内层氧化度一般保留「的」（如 `Waxed Exposed Copper` → `涂蜡的斑驳铜块`）。
- **可疑的**：`Suspicious <方块>` 译作 `可疑的<方块>`，须保留「的」（如 `Suspicious Sand` → `可疑的沙子`）；`Suspicious Stew` 例外，译作 `谜之炖菜`。
- **粗金属与失活珊瑚**：`raw_iron / raw_gold / raw_copper` 系列的 `Raw <Metal>` 译作 `粗<金属>`，不加「的」（如 `Raw Iron` → `粗铁`）；`Dead <... Coral>` 一律译作 `失活的<...珊瑚>`（带「的」）。
- **加工状态与材质前缀**：下列固定前缀不加「的」——`Stripped`（去皮……）、`Polished`（磨制……）、`Chiseled`（雕纹……，1.19.2 及更早版本为 `錾制…`）、`Cracked`（裂纹……）、`Cut`（切制……）、`Smooth`（平滑……）、`Mossy`（苔……，如 `Mossy Cobblestone` → `苔石`）、`Infested`（虫蚀……）、`Waxed`（涂蜡……）。

## 3. 树木、木材与竹子

树木名词根随所指对象在译文中增减「树」「木」。`terms-v1.tsv` 只收基础树种（多字树名收基础名，单字树根收 `X木|X树`），具体构词按以下三类处理：

- **单字树根（核心词根只有一字，必须补成双音节）**：`Oak`（橡）、`Dark Oak`（深色橡）、`Pale Oak`（苍白橡）、`Poplar`（杨）。
  - **树叶与树苗**：词根后加「树」，即 `<X>树树叶`、`<X>树树苗`（如 `Oak Leaves` → `橡树树叶`、`Dark Oak Sapling` → `深色橡树树苗`）。
  - **原木、木板、木材与木制品**：词根后加「木」，即 `<X>木原木`、`<X>木木板`、`<X>木<制品>`；其中 `<Tree> Wood` 本身即 `<X>木`（如 `Oak Wood` → `橡木`、`Oak Planks` → `橡木木板`、`Pale Oak Wood` → `苍白橡木`、`Poplar Wood` → `杨木`）。
- **多字树名（基础名已成双音节）**：`Spruce`（云杉）、`Birch`（白桦）、`Jungle`（丛林）、`Acacia`（金合欢）、`Cherry`（樱花）、`Mangrove`（红树）、`Crimson`（绯红）、`Warped`（诡异）。
  - **树木与专属部件**：`Leaves`（树叶）、`Sapling`（树苗）、`Log`（原木）、`Planks`（木板）、`Propagule`（胎生苗）、`Roots`（根）、`Stem`（菌柄）、`Hyphae`（菌核）本身已带材质或部位词素，直接拼在基础名后（如 `云杉树叶`、`云杉原木`、`云杉木板`、`红树树叶`、`红树原木`、`红树木板`、`红树根`、`绯红菌柄`、`诡异菌核`）。
  - **木材（`<Tree> Wood`）与通用制品**：门、船、台阶、栅栏等通用制品不自带材质语素，需在基础名后加「木」成 `<X>木` 或 `<X>木<制品>`（如 `云杉木`、`金合欢木船`、`白桦木台阶`、`红树木`、`红树木船`、`诡异木活板门`）。
  - **群系特例**：`Birch Forest` → `桦木森林`（省「白」）、`Old Growth Pine Taiga` → `原始松木针叶林`、`Mangrove Swamp` → `红树林沼泽`。
- **竹（`Bamboo`，非木材）**：独立物品与盆栽为 `竹子` 和 `竹子盆栽`；竹制品前缀一律减为单字 `竹`（如 `竹块`、`竹门`、`竹台阶`、`竹筏`、`竹马赛克`），其中 `Bamboo Planks` 减字为 `竹板`。

## 4. 高歧义通名（砖、石、桶、盔甲）

这几类通名在独立物品与复合词之间存在系统性的减字或特称切换，不适合靠单字短变体留在术语表内，按下列语境规则把关：

- **砖与砖块（`Brick` / `Bricks`）**：
  - 独立红砖物品 `Brick` → `红砖`、方块 `Bricks` → `红砖块`，成套衍生方块 `Brick Slab/Stairs/Wall` → `红砖台阶/楼梯/墙`。
  - 作复合词定语时，`Brick` 统一译为 `砖`（`Nether Brick` → `下界砖`、`Resin Brick` → `树脂砖`、`Deepslate Brick Slab` → `深板岩砖台阶`）。
  - 复数 `Bricks` 在存在同名单片砖物品时译为 `砖块`（`Nether Bricks` → `下界砖块`、`Resin Bricks` → `树脂砖块`、`Red Nether Bricks` → `红色下界砖块`）；不存在同名单片砖物品时统一译为 `砖`（`Stone Bricks` → `石砖`、`Deepslate Bricks` → `深板岩砖`、`Mud Bricks` → `泥砖`、`Tuff Bricks` → `凝灰岩砖`、`Prismarine Bricks` → `海晶石砖`、`Quartz Bricks` → `石英砖`）。
- **石头与石质（`Stone`）**：独立方块 `Stone`、平滑变体与石制常规方块（`Stone Slab/Stairs/Button/Pressure Plate`、`Smooth Stone`、`Infested Stone`）用 `石头`；作石质工具武器（`Stone Sword/Pickaxe/Axe/Shovel/Hoe/Spear` → `石剑/石镐/石斧/石锹/石锄/石矛`）及复合砖石词素（`Stone Bricks` → `石砖`、`End Stone` → `末地石`）时减字为 `石`。
- **桶（`Bucket`）**：空桶独立物品 `Bucket` → `铁桶`；装填物或生物的复合桶统一用 `桶`（`Water Bucket` → `水桶`、`Lava Bucket` → `熔岩桶`、`Milk Bucket` → `奶桶`、`Powder Snow Bucket` → `细雪桶`、`Bucket of Axolotl` → `美西螈桶`）。
- **盔甲与护甲（`Armor`）**：属性名 `Armor` → `护甲值`；穿戴装备、纹饰与常规语境用 `盔甲`（`Armor Stand` → `盔甲架`、`Armor Toughness` → `盔甲韧性`）；坐骑护甲用 `…铠`（`Horse Armor` → `马铠`、`Nautilus Armor` → `鹦鹉螺铠`）。

## 5. 容器、载体与附着体例

- **墙上附着方块**：key 含 `wall_sign`、`wall_hanging_sign`、`wall_banner`、`wall_torch`、`wall_fan`、`wall_skull`、`wall_head` 的 `Wall <X>` 一律译作 `墙上的<X>`（如 `Wall Torch` → `墙上的火把`、`Acacia Wall Sign` → `墙上的金合欢木告示牌`）。注意 `X Wall` 是石墙/砖墙，译作 `<X>墙`（如 `Andesite Wall` → `安山岩墙`），不套用此条。
- **盆栽**：`potted_*` 的 `Potted <Plant>` 译作 `<植物>盆栽`（如 `Potted Allium` → `绒球葱盆栽`），不用 `盆栽的…`。
- **刷怪蛋**：`*_spawn_egg` 的 `<Mob> Spawn Egg` 统一为 `<生物>刷怪蛋`。
- **运输与载体**：`<X> with Chest` 视载体惯例译作 `运输<X>`（如 `Minecart with Chest` → `运输矿车`、`Oak Boat with Chest` → `橡木运输船`、`Bamboo Raft with Chest` → `运输竹筏`）；其余载人/装物矿车为 `<X>矿车`（如 `Minecart with TNT` → `TNT矿车`、`Minecart with Hopper` → `漏斗矿车`）。
- **药水与药箭**：普通药水 `Potion of <Effect>` 为 `<效果>药水`，喷溅型加前缀 `喷溅型<效果>药水`，滞留型加前缀 `滞留型<效果>药水`；药箭 `Arrow of <Effect>` 为 `<效果>之箭`（基础未合成药水/药箭除外：`粗制的药水`、`不可合成的药水`、`药箭`、`不可合成的药箭`）。

## 6. 旗帜图案与特殊域构词

- **旗帜图案颜色嵌槽（替代原 `special/terms-banner.tsv`）**：所有 16 种颜色在下列嵌槽格局以及 `Cross`（正十字）、`Saltire`（斜十字）、`Paly`（竖条纹）中**一律省去「色」字**（无论单字色如 `黑/白/红`，还是双字色如 `淡蓝/淡灰/黄绿/品红/粉红`）；其余独立格局一律采用 `<颜色>色<图案>` 前置。
  - **去「色」嵌槽与固定格局**（`<C>` 为去「色」后的颜色名，如 `黑`、`淡蓝`）：
    - 满底 `Fully <C> Field` → `<C>底`
    - 横条：`Base` → `底<C>横条`、`Fess` → `中<C>横条`、`Chief` → `顶<C>横条`
    - 竖条：`Pale` → `中<C>竖条`、`Pale Dexter` → `右<C>竖条`、`Pale Sinister` → `左<C>竖条`
    - 斜条：`Bend` → `右<C>斜条`、`Bend Sinister` → `左<C>斜条`
    - 方角：`Base Dexter Canton` → `右底<C>方`、`Base Sinister Canton` → `左底<C>方`、`Chief Dexter Canton` → `右顶<C>方`、`Chief Sinister Canton` → `左顶<C>方`
    - 三角：`Chevron` → `底<C>三角`、`Inverted Chevron` → `顶<C>三角`
    - 十字与条纹：`Cross` → `<C>正十字`、`Saltire` → `<C>斜十字`、`Paly` → `<C>竖条纹`
  - **保留 `<颜色>色` 前置的格局**：
    - 边框与波纹：`Bordure`（方框边）、`Bordure Indented`（波纹边）、`Base Indented`（底波纹）、`Chief Indented`（顶波纹）
    - 几何与渐淡：`Field Masoned`（砖纹）、`Roundel`（圆形）、`Lozenge`（菱形）、`Gradient`（自上渐淡）、`Base Gradient`（自下渐淡）
    - 对半与斜分：`Per Fess`（上半方形）、`Per Fess Inverted`（下半方形）、`Per Pale`（右半方形）、`Per Pale Inverted`（左半方形）、`Per Bend`（左上三角）、`Per Bend Sinister`（右上三角）、`Per Bend Inverted`（右下三角）、`Per Bend Sinister Inverted`（左下三角）
    - 徽章图案：`Creeper Charge`（苦力怕盾徽）、`Flower Charge`（花朵盾徽）、`Skull Charge`（头颅盾徽）、`Thing`（`Mojang徽标`）、`Snout`（猪鼻）、`Globe`（地球）、`Flow`（涡流）、`Guster`（旋风）
  - **旗帜图案物品**：`<Pattern> Banner Pattern` 译作 `<图案>旗帜图案`（如 `Field Masoned Banner Pattern` → `砖纹旗帜图案`）。
- **陶片与盔甲纹饰**：陶片物品统一为 `<纹样>纹样陶片`；盔甲纹饰统一为 `<纹样>盔甲纹饰`，盔甲纹饰材料 `<X> Material` 统一为 `<X>质`（如 `Amethyst Material` → `紫水晶质`）。两类纹样原型各自查对应 `special/` 分表（如 `Flow` 在陶片与旗帜中为 `涡流`，`Explorer` 在陶片中为 `探险`、在探险家地图中为 `探险家`）。

## 7. 功能文本体例

- **字幕**：声音字幕统一为 `<发声主体>：<动作或声音>`，中间用全角冒号 `：` 且不留空格（如 `Amethyst chimes` → `紫水晶：叮铃`）。带动词歧义或主谓倒改的整句按动作自然译出（如 `Bee leaves hive` → `蜜蜂：离巢`、`Goat Horn breaks off` → `山羊：断角`、`Fireball whooshes` → `火焰弹：呼啸`）；无明确主体的环境/通用音效直接写名词或动作（如 `Eerie noise` → `怪异的噪声`、`Splashing` → `溅起水花`）。交互类字幕可按实际语义意译（如 `Lever clicks` → `拉杆：拉动`）。
- **统计项**：次数类统计收尾用 `…次数`（如 `Animals Bred` → `繁殖动物次数`），距离类统计收尾用 `…距离`（如 `Distance by Boat` → `坐船移动距离`）。
- **死亡消息**：保持紧凑陈述句，句末不加句号（如 `%1$s was shot by %2$s` → `%1$s被%2$s射杀`）。
- **进度**：标题偏四字或简练名词性短语，描述多用无主语祈使短语且句末不加句号（如 `Discover every biome` → `发现所有的生物群系`）。

## 8. 标点与空格

- **中西文与占位符间距**：中文与英文缩写、数字及 `%s` / `%1$s` 等格式化占位符之间**不加空格**（如 `TNT爆炸已禁用`、`%1$s被%2$s射杀`、`自定义Boss栏%s现为可见`）。仅极少数保留英文书名/署名格式（如 `%1$s 著`）按英文空格习惯处理。
- **全角标点**：说明性冒号、括号、引号统一用全角（`：`、`（）`、`“”`），命令或语法示例中的半角符号（如 `'/perf stop'`）保持半角。
