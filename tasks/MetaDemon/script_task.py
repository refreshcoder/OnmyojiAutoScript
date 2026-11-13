# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property
from datetime import datetime, timedelta
from time import sleep


from module.base.timer import Timer
from module.logger import logger
from module.exception import TaskEnd


from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.battle import Battle
from tasks.Component.GeneralBattle.battle_wait import (
    BattleResult, HookSignal, PerTaskPreset, PrivateContext, PublicContext,
    battle_wait_strategy, battle_wait_options, runtime,
)
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.MetaDemon.config import MetaDemon, DefaultStrategy, Strategy, ShareStar
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.Restart.assets import RestartAssets
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets



class Star56(GameUi, MetaDemonAssets):

    @cached_property
    def cached_strategies(self) -> dict[str, list[int]]:
        return Strategy.parse_all(self.config.meta_demon.md_strategies)

    @cached_property
    def cached_default_group_team(self) -> list[int]:
        return Strategy.parse_group_team(self.config.meta_demon.md_default_strategy.md_preset_group_team_default_1) \
            + Strategy.parse_group_team(self.config.meta_demon.md_default_strategy.md_preset_group_team_default_2)

    def is_star56(self):
        if not self.appear(self.I_STAR56_POS_1):
            return True
        return False

    def hp_threshold_low(self, image):
        """
        @param image:
        @return: 血量小于阈值返回True
        """
        return self.appear(self.I_STAR56_HP_THRESHOLD_F) and not self.appear(self.I_STAR56_HP_THRESHOLD_T)

    @classmethod
    def strategy2group_team(cls, strategies: dict[str, list[int]], detect_name: str) -> list[int] | None:
        """
        先是默认的完全匹配，然后是1个字符不同，最后是2个字符不同
        @param strategies:
        @param detect_name:
        @return:
        """
        for i in range(2):
            for key_name in strategies:
                if len(key_name) != len(detect_name):
                    continue
                diff_count = sum(1 for c1, c2 in zip(key_name, detect_name) if c1 != c2)
                if diff_count <= i < len(detect_name):
                    return strategies[key_name]
        return None

    def get_group_team(self, detect_name: str) -> list[int]:
        tmp = self.strategy2group_team(self.cached_strategies, detect_name)
        return tmp if tmp else self.cached_default_group_team


class ScriptTask(RightActivity, Battle, GeneralBattle, GeneralInvite, SwitchSoul, Star56):

    def run(self):
        if self.config.meta_demon.switch_soul.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(self.config.meta_demon.switch_soul.switch_group_team)

        if self.config.meta_demon.switch_soul.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(self.config.meta_demon.switch_soul.group_name,
                                         self.config.meta_demon.switch_soul.team_name)

        self.enter(self.I_RIGHT_ENTER)
        while 1:
            self.screenshot()
            if self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON):
                break

            if self.ui_reward_appear_click():
                continue
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1.5):
                continue
            if self.appear_then_click(self.I_ENTER_ENSURE, interval=1):
                continue
            if self.appear_then_click(self.I_ENTER2, interval=1):
                continue
        if self.config.meta_demon.meta_demon_config.meta_crafting_card:
            self.crafting()

        share_config = self.config.meta_demon.md_share
        only_summon_and_share = self.config.meta_demon.meta_demon_config.only_summon_and_share
        if share_config.enable and not only_summon_and_share:
            logger.warning('Share is enabled but only_summon_and_share is off; '
                           'sharing is only available in summon & share only mode')

        # 只召唤并分享鬼王，不自己战斗
        if only_summon_and_share:
            success = self.run_summon_and_share()
            self.exit_meta_demon()
            logger.info('Exit MetaDemon (summon & share only)')
            # 这次只处理一只鬼王，鬼王被好友击杀后再由调度器重新召唤
            delay = share_config.interval if success else max(share_config.interval, 30)
            self.set_next_run(task="MetaDemon", success=success,
                              target=datetime.now() + timedelta(minutes=delay))
            raise TaskEnd

        boss_timer = Timer(50)
        boss_timer.start()
        first_battle_for_easy_boss = True
        while 1:
            battle_processing = False
            is_hard_boss = False  # 五星或者六星
            self.screenshot()
            if not (self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON)):
                continue

            # 先看自己有没有鬼王要打
            if (not self.appear(self.I_BOSS_EMPTY) and
                    (self.appear(self.I_BOSS_CONVENE) or self.appear(self.I_BOOS_PUBLIC))):
                logger.info('Try to battle boss from self')
                self.click(self.I_BOSS_EMPTY, interval=1.5)
                battle_processing = True
                if self.is_star56():
                    is_hard_boss = True
            # 看别人的是否给我共享鬼王
            if not battle_processing and self.config.meta_demon.meta_demon_config.auto_shared_boss:
                if not self.appear(self.I_BOSS_EMPTY_1) and self.ocr_appear(self.O_BOSS_EMPTY_1):
                    logger.info('Try to battle boss 1 from others')
                    self.click(self.I_BOSS_EMPTY_1, interval=1.5)
                    self.ui_click(self.I_BOSS_EMPTY_1, stop=self.I_BATTLE_DEMON, interval=1.5)
                    battle_processing = True
                    is_hard_boss = True
                elif not self.appear(self.I_BOSS_EMPTY_2):
                    logger.info('Try to battle boss 2 from others')
                    self.click(self.I_BOSS_EMPTY_2, interval=1.5)
                    self.ui_click(self.I_BOSS_EMPTY_1, stop=self.I_BATTLE_DEMON, interval=1.5)
                    battle_processing = True
                    is_hard_boss = True
            # 是否喝茶 疲劳满了就不打了
            current_exhaustion = self.current_exhaustion()
            if current_exhaustion > 100:
                if self.config.meta_demon.meta_demon_config.auto_tea:
                    logger.info('Exhaustion is full, buy tea')
                    boss_timer.reset()
                    self.buy_tea()
                else:
                    logger.info('Exhaustion is full, exit')
                    break
            # 超时结束
            if boss_timer.reached():
                logger.info('Time out, exit')
                break
            # 5/6星特殊处理 + 使用自定义策略组
            target_group_team = [None, None]
            if is_hard_boss:
                logger.info('Hard boss')
                if self.config.meta_demon.meta_demon_config.md_use_strategy:
                    detect_full_name = self.O_MD_FULL_NAME.ocr_single(self.device.image)
                    logger.info(f'detect_full_name: {detect_full_name}')
                    if not detect_full_name:
                        detect_full_name = ''
                    group_team = self.get_group_team(detect_full_name)
                    if self.hp_threshold_low(self.device.image):
                        logger.info('Hp threshold low')
                        target_group_team = group_team[2:4]
                    else:
                        logger.info('Hp threshold high')
                        target_group_team = group_team[0:2]
            else:
                if self.config.meta_demon.meta_demon_config.md_use_strategy and first_battle_for_easy_boss:
                    logger.info('Normal boss first battle use default group team')
                    target_group_team = self.cached_default_group_team
            if battle_processing and self.appear(self.I_BATTLE_DEMON):
                logger.info(f'preset group team: {target_group_team}')
                self.battle_boss(target_group_team[0], target_group_team[1])
                if first_battle_for_easy_boss:
                    first_battle_for_easy_boss = False
                if is_hard_boss:
                    first_battle_for_easy_boss = True
                boss_timer.reset()
                continue

            # 自己召唤鬼王
            if current_exhaustion < 90 and self.find_demon():
                boss_timer.reset()
                continue

        # 退出
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MAIN, interval=1.4)
        logger.info('Exit MetaDemon')
        self.set_next_run(task="MetaDemon", success=True)
        raise TaskEnd

    # ------------------------------------------------------------------------------------------------------------------
    # 只召唤 + 分享
    # ------------------------------------------------------------------------------------------------------------------
    @property
    def share_entry(self):
        """分享入口：鬼王卡片上的“集结”（实机 1280x720 抓图，匹配 0.999）"""
        return self.I_BOSS_CONVENE

    @property
    def share_confirm(self):
        """集结面板的邀请按钮（与 GeneralInvite 的 I_INVITE_ENSURE 是同一张图，实机 0.999）"""
        return self.I_INVITE_ENSURE

    @property
    def share_panel(self):
        """集结面板是否已打开：只有这个面板有邀请按钮"""
        return self.I_INVITE_ENSURE

    def run_summon_and_share(self) -> bool:
        """
        本次运行只做两件事：召唤鬼王、把鬼王分享给 md_share.friends 里的玩家。
        不进入战斗，也不处理别人的鬼王。
        """
        logger.hr('MetaDemon summon & share only', 1)

        # 1. 已经有自己的鬼王：只补分享，不召唤
        if self.own_boss_exists():
            if self.appear(self.I_BOOS_PUBLIC):
                logger.info('Own boss is already public, skip share')
            else:
                logger.info('Own boss exists, only try to share')
                self.share_demon()
            return True

        # 2. 没有鬼王，检查召唤门票
        if not self.has_summon_ticket():
            logger.warning('No summon ticket, skip this run')
            return False

        # 3. 召唤
        if not self.find_demon(timeout=60):
            logger.warning('Summon demon failed')
            return False

        # 4. 分享
        self.share_demon()
        return True

    def own_boss_exists(self) -> bool:
        """当前是否已经有一只自己的鬼王"""
        self.screenshot()
        # 鬼王详情页（挑战按钮可见）说明已经有鬼王
        if self.appear(self.I_BATTLE_DEMON):
            return True
        # 主界面：I_BOSS_EMPTY 出现表示自己的鬼王槽位是空的
        return not self.appear(self.I_BOSS_EMPTY)

    def has_summon_ticket(self) -> bool:
        """检查召唤鬼王所需门票；OCR 失败时返回 True，交给召唤流程兜底"""
        self.screenshot()
        current, remain, total = self.O_MD_TICKET.ocr(self.device.image)
        logger.info(f'Summon ticket: current={current}, remain={remain}, total={total}')
        if total <= 0:
            logger.warning('Summon ticket OCR failed, try summon anyway')
            return True
        return current > 0

    def share_demon(self) -> bool:
        """
        把自己的鬼王分享给配置里的指定玩家。

        入口说明：
          - 主界面鬼王卡片上的“集结”图标（I_BOSS_CONVENE）目前先作为分享入口；
          - 好友面板的“确定/邀请”按钮复用 GeneralInvite 的 I_INVITE_ENSURE；
          - 如果实机发现入口或确认按钮不是这两个图，需要按实际截图补充
            I_MD_SHARE / I_MD_SHARE_ENSURE 后再替换这里。
                """
        con = self.config.meta_demon.md_share
        if not con.enable:
            logger.info('Share demon is disabled')
            return False

        friends = con.parse_friends()
        if not friends:
            logger.info('Share demon: no friend configured')
            return False

        # 没在详情页时先进入详情页，is_star56 依赖详情页的星级标记
        if not self.enter_boss_detail():
            logger.warning('Share demon: enter boss detail failed')
            return False

        if con.share_star != ShareStar.ALL:
            is_star56 = self.is_star56()
            if con.share_star == ShareStar.STAR_1_4 and is_star56:
                logger.info('Share demon: 5/6 star, skip (only share 1-4 star)')
                return False
            if con.share_star == ShareStar.STAR_5_6 and not is_star56:
                logger.info('Share demon: not 5/6 star, skip (only share 5-6 star)')
                return False

        shared = []
        for name in friends:
            if not self.open_share_panel():
                # 分享入口消失：一般是次数用完 / 已经分享过 / 该鬼王不可分享
                logger.info('Share demon: share entry not found, stop')
                break
            if self.share_to_friend(name):
                shared.append(name)
                logger.info(f'Share demon: share to [{name}] success')
            else:
                logger.warning(f'Share demon: share to [{name}] failed')

        if shared:
            self.config.notifier.push(
                content=f'鬼王已分享给: {", ".join(shared)}', title='超鬼王')
        return bool(shared)

    def enter_boss_detail(self) -> bool:
        """从主界面点自己的鬼王卡片进入详情页"""
        if self.appear(self.I_BATTLE_DEMON):
            return True
        timer = Timer(10).start()
        while 1:
            self.screenshot()
            if self.appear(self.I_BATTLE_DEMON):
                return True
            if timer.reached():
                logger.warning('Share demon: enter boss detail timeout')
                return False
            # I_BOSS_EMPTY 这里是借用空槽位的坐标来点自己的鬼王卡片
            self.click(self.I_BOSS_EMPTY, interval=2)

    def open_share_panel(self) -> bool:
        """点集结按钮，直到集结面板真的打开（面板标志 = 邀请按钮可见）"""
        timer = Timer(10).start()
        while 1:
            self.screenshot()
            if self.appear(self.share_panel):
                return True
            if timer.reached():
                break
            if self.appear_then_click(self.share_entry, interval=1.5):
                continue

        # 详情页：进入详情后再尝试一次
        if not self.enter_boss_detail():
            return False
        timer.reset()
        while 1:
            self.screenshot()
            if self.appear(self.share_panel):
                return True
            if timer.reached():
                break
            if self.appear_then_click(self.share_entry, interval=1.5):
                continue

        logger.warning('Share demon: open convene panel failed, '
                       'check I_BOSS_CONVENE / I_INVITE_ENSURE assets')
        return False

    def share_to_friend(self, name: str) -> bool:
        """
        在已经打开的集结面板里选中 name，然后点邀请。
        先找“好友”页，找不到再找“寮友”页（点选后需看到青色菱形勾才算选中）。
        """
        selected = False
        for index in (1, 2):
            if not self.switch_friend_tab(index):
                continue
            if self.detect_select(name):
                selected = True
                break

        if not selected:
            logger.warning(f'Share demon: [{name}] not found in any tab')

        # 不论是否选中都要点邀请，否则面板关不掉
        self.click_invite()
        return selected

    def detect_select(self, name: str = None) -> bool:
        """
        在集结面板里选中好友 name。

        不走 GeneralInvite.detect_select：那边用 I_SELECTED（邀请面板的勾，ROI 在右列第三行）
        且 while 没有超时——集结面板里点了名字但匹配不到 I_SELECTED 会无限重点。
        这里改成最多 3 轮，每轮点完只等 2s 的菱形勾。
        """
        if not name:
            return False

        for _ in range(3):
            self.screenshot()
            self.O_FRIEND_NAME_1.keyword = name
            self.O_FRIEND_NAME_2.keyword = name
            clicked = self.ocr_appear_click(self.O_FRIEND_NAME_1, interval=1, exact=True)
            clicked = self.ocr_appear_click(self.O_FRIEND_NAME_2, interval=1, exact=True) or clicked
            if not clicked:
                logger.info(f'Share demon: [{name}] not in current tab')
                return False
            timer = Timer(2).start()
            while not timer.reached():
                self.screenshot()
                if self.appear(self.I_BOSS_CONVENE_SELECTED):
                    return True
            logger.warning(f'Share demon: clicked [{name}] but no selected mark, retry')
        return False

    def click_invite(self) -> bool:
        """点邀请并等面板关闭；关不掉就再点，最多 3 次"""
        for _ in range(3):
            self.screenshot()
            if not self.appear(self.share_confirm):
                return True
            self.click(self.share_confirm, interval=1)
            timer = Timer(3).start()
            while not timer.reached():
                self.screenshot()
                if not self.appear(self.share_confirm):
                    return True
        logger.warning('Share demon: invite clicked but panel still open')
        return False

    def switch_friend_tab(self, index: int) -> bool:
        """
        切到好友(index=1) / 寮友(index=2) 页。
        以 tab 的“选中态”资产为准（未选中的 tab 是淡色，匹配不上）。
        """
        if index == 1:
            click, active = self.C_CONVENE_TAB_1, self.I_BOSS_CONVENE_TAB_1
        else:
            click, active = self.C_CONVENE_TAB_2, self.I_BOSS_CONVENE_TAB_2
        timer = Timer(4).start()
        while 1:
            self.screenshot()
            if self.appear(active):
                return True
            if timer.reached():
                logger.warning(f'Share demon: switch to tab {index} timeout')
                return False
            if self.click(click, interval=1):
                continue

    def exit_meta_demon(self):
        """退出超鬼王活动，回到庭院"""
        self.screenshot()
        if self.appear(self.I_CHECK_MAIN):
            return

        # 正常情况下面板已经关了；异常时兜底关一次
        self.ui_click_until_disappear(self.share_confirm, interval=1)

        # 详情页 / 活动主页：通用返回，直到回到庭院
        timer = Timer(15).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CHECK_MAIN):
                return
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1.5):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1.4):
                continue
            break

        logger.warning('Exit MetaDemon timeout')

    def current_exhaustion(self) -> int:
        self.screenshot()
        cu, res, total = self.O_MD_EXHAUSTION.ocr(self.device.image)
        return int(cu)

    def buy_tea(self):
        pass

    def crafting(self):
        """
        把一星合成二星
        @return:
        """
        logger.info('Star crafting 1 star to 2 star')
        self.ui_click(self.I_CRAFTING_1, self.I_CRAFTING_START, interval=1.5)
        timer = Timer(3).start()
        count = 0
        while 1:
            self.screenshot()
            if self.ui_reward_appear_click():
                timer.reset()
                continue
            if timer.reached() or count > 3:
                break
            if not self.ocr_appear(self.O_CRAFTING_CARD_1):
                break
            if self.appear(self.I_CRAFTING_EMPTY) or self.appear(self.I_CRAFTING_EMPTY_NEW):
                if self.appear_then_click(self.I_CRAFTING_CARD_STAR_1, interval=1):
                    continue
            else:
                self.appear_then_click(self.I_CRAFTING_START, interval=3)
                count += 1
                timer.reset()
                continue
        logger.info('Finish star crafting')
        self.ui_click_until_disappear(self.I_UI_BACK_RED, interval=1)
        sleep(0.5)

    def find_demon(self, timeout: float = None) -> bool:
        """
        召唤鬼王
        @param timeout: 召唤超时时间（秒），None 表示不超时（保持原有行为）
        @return:
        """
        logger.info('Find demon')
        timer = Timer(timeout).start() if timeout else None
        while 1:
            self.screenshot()
            if self.appear(self.I_BATTLE_DEMON) and not self.appear(self.I_BOSS_EMPTY):
                break
            if timer and timer.reached():
                logger.warning('Find demon timeout')
                return False
            if self.appear_then_click(self.I_FIND_DEMON, interval=3.5):
                continue
        self.screenshot()
        if self.is_star56():
            logger.info('Star 5 or 6 demon found')
            timer = Timer(10).start()
            detect_full_name = ''
            while 1:
                sleep(0.4)
                self.screenshot()
                detect_full_name = self.O_MD_FULL_NAME.ocr_single(self.device.image)
                if detect_full_name:
                    break
                if timer.reached():
                    logger.warning('OCR demon name timeout')
                    break
            logger.info(f'召唤到高星鬼王: {detect_full_name}')
            self.config.notifier.push(content=f'召唤到高星鬼王: {detect_full_name}', title='超鬼王')
        return True

    def battle_boss(self, group: int = None, team: int = None) -> bool:
        """
        战斗流程不再自己写 while 循环，全部交给 battle_wait 的策略化钩子：
          prepare/preset  准备阶段与预设队伍（5/6 星按推荐阵容切队）
          success/failure 超鬼王自带的结算界面（I_MD_WIN / I_MD_BATTLE_FAILURE）
          idle            战斗中给鬼王上标记
        @param group: 预设组，与 team 同时为 None 时不切预设队伍
        @param team:  预设队伍，与 group 同时为 None 时不切预设队伍
        @return: True 战斗胜利，False 战斗失败
        """
        logger.info('Battle boss')
        self.ui_click(self.I_TEAM_LOCK, self.I_TEAM_UNLOCK, interval=1.5, timeout=5)
        self.ui_click_until_disappear(self.I_BATTLE_DEMON, interval=1.8)
        # 任务级战斗计数：本场是第几场（和旧日志 Current count 对齐）
        count = runtime.pub_ctx.per_task.count if runtime.pub_ctx else 0
        logger.info(f'Current count: {count + 1}')

        battle_config = GeneralBattleConfig()
        battle_config.lock_team_enable = False
        # 针对5/6星的挑战
        if group is not None and team is not None:
            battle_config.preset_enable = True
            battle_config.preset_group = group
            battle_config.preset_team = team
            # 每只5/6星鬼王的推荐阵容不同，而预设队伍默认是按任务只切一次的，
            # 这里只复位 preset 的任务级状态，per_task.count 保持累加
            PerTaskPreset.reset_preset_state(self)

        strategies, options = self.loadout_from_config(battle_config)
        strategies['success'] = 'metademon'
        strategies['failure'] = 'metademon'
        strategies['idle'] = 'metademon'
        options['completion'].check_imgs = [self.I_CRAFTING_1, self.I_FIND_DEMON, self.I_BATTLE_DEMON]

        self.loadout_show((strategies, options))
        self.boss_mark_reset()
        with battle_wait_strategy(**strategies), battle_wait_options(**options):
            win = self.battle_wait()
        logger.info(f'Battle boss win: {win}, current count: {runtime.pub_ctx.per_task.count}')
        return win

    # ------------------------------------------------------------------------------------------------------------------
    # battle_wait 钩子：超鬼王自己的结算界面与战中行为
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_success_metademon(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        if not self.appear(self.I_MD_WIN):
            return HookSignal.CONTINUE
        logger.info('Win battle')
        while 1:
            self.screenshot()
            if not self.appear(self.I_MD_WIN):
                break
            self.click(self.I_MD_WIN)
            sleep(0.5)
        pub.per_battle.success = BattleResult.SUCCESS
        return runtime.hook_enabled_update(
            enable=('completion',),
            disable=('success', 'failure'),
        )

    def _bw_failure_metademon(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        if not self.appear(self.I_MD_BATTLE_FAILURE):
            return HookSignal.CONTINUE
        logger.warning('False battle')
        self.ui_click_until_disappear(self.I_MD_BATTLE_FAILURE)
        pub.per_battle.success = BattleResult.FAILURE
        return runtime.hook_enabled_update(
            enable=('completion',),
            disable=('success', 'failure'),
        )

    def _bw_idle_metademon(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        if self.is_in_real_battle(False):
            self.boss_mark()
        return HookSignal.CONTINUE


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()

