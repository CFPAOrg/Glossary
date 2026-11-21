# 原版非直译固定句式备忘

整理自 `Vanilla/latest.tsv`，记录 `Vanilla/terms/STYLE.md` 之外无法由英文直译推出的特定界面短语与代表性意译文案，供校对参考。

## 特定界面短语与模板

- **附魔台花费增译（4 条）**：`container.enchant.lapis.*`（`%s Lapis Lazuli` → `花费：%s颗青金石`），`container.enchant.level.*`（`%s Enchantment Levels` → `+ %s级经验`）。
- **配方书筛选增“仅”（4 条）**：`gui.recipebook.toggleRecipes.{craftable,blastable,smeltable,smokable}`（`Showing Craftable` 等 → `仅显示可合成/可冶炼/可烧炼/可熏制`，对照 `Showing All` → `显示全部`）。
- **补单位或改序的紧凑模板**：`options.fullscreen.entry`（`%sx%s@%s (%sbit)` → `%s×%s@%sHz（%s位色深）`），`debug.crash.warning`（`Crashing in %s...` → `将在%s秒后崩溃…`），`stat_type.minecraft.killed`（`You killed %s %s` → `你杀死了%2$s%1$s次`），`commands.scoreboard.players.get.success`（`%s has %s %s` → `%1$s在%3$s记分项里拥有%2$s分`），`narration.suggestion`（`已选中%2$s项建议中的第%1$s项：%3$s`）。
- **其余单条固定短语**：`multiplayer.status.and_more`（`... and %s more ...` → `…及其他%s名玩家…`），`book.pageIndicator`（`Page %1$s of %2$s` → `第%1$s页/共%2$s页`），`potion.whenDrank`（`When Applied:` → `当生效后：`）。

## 单条高度意译与归化文案（代表项）

- `compliance.playtime.message`：`Excessive gaming may interfere with normal daily life` → `适度游戏益脑，沉迷游戏伤身`
- `sleep.not_possible` / `sleep.skipping_night`：`No amount of rest can pass this night` → `已入睡玩家的数量不足以跳过夜晚`；`Sleeping through this night` → `今夜将在睡梦中度过`
- `options.graphics.warning.cancel`：`Take Me Back` → `算了`
- `options.fov.max` / `options.fov.min`：`Quake Pro` → `广角`；`Normal` → `中`
- `options.difficulty.peaceful.info` / `options.difficulty.hard.info`：`No hostile mobs and only some neutral mobs spawn.` → `不会生成绝大多数敌对生物。`；`...drains all health.` → `饥饿值耗尽后最终会饿死。`
- `selectWorld.backupWarning.experimental`：`Here be dragons!` → `务必谨慎！`
- `selectWorld.gameMode.spectator.info`：`You can look but don't touch.` → `你可以旁观，但不能互动。`
- `title.credits`：`Copyright Mojang AB. Do not distribute!` → `© Mojang AB 请勿二次分发！`
- `multiplayer.stopSleeping` / `multiplayer.status.pinging` / `multiplayer.status.motd.narration`：`Leave Bed` → `起床`；`Pinging...` → `检测中…`；`Message of the day: %s` → `服务器信息：%s`
- `item.intangible`：`Intangible` → `不可回收`
- `mco.time.now` / `mco.configure.world.invite_codes.expiration.never`：`right now` → `刚刚`；`Never` → `始终有效`
- `advMode.mode.*`：`Always Active` → `保持开启`、`Conditional` → `条件制约`、`Unconditional` → `不受制约`、`Needs Redstone` → `红石控制`
- `death.attack.*`（突出意译）：`inFire`（`went up in flames` → `浴火焚身`）、`mace_smash`（`was smashed by %2$s` → `被%2$s一锤毙命`）、`outOfWorld.player`（`didn't want to live in the same world as %2$s` → `与%2$s不共戴天`）、`even_more_magic`（`was killed by even more magic` → `被不为人知的魔法杀死了`）、`fireworks`（`went off with a bang` → `随着一声巨响消失了`）

## 范围说明

- 排查覆盖 `Vanilla/latest.tsv` 的 UI、容器、选项、死亡消息、命令短句、Realms 短句与测试提示；长段 `mco`（>55 字符）与长条 `commands`/`gamerule.description` 未逐行细读，单条意译清单为保守代表集而非全集。
