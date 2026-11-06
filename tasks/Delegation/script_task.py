# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_delegation
from tasks.Delegation.config import DelegationConfig
from tasks.Delegation.assets import DelegationAssets


class ScriptTask(GameUi, DelegationAssets):

    def run(self):
        self.goto_page(page_delegation)
        self.check_reward()
        con: DelegationConfig = self.config.delegation.delegation_config
        if con.miyoshino_painting:
            self.delegate_one('画')
        if con.bird_feather:
            self.delegate_one('鸟羽')
        if con.find_earring:
            self.delegate_one('寻找耳环')
        if con.cat_boss:
            self.delegate_one('猫老大')
        if con.miyoshino:
            self.delegate_one('接送')
        if con.strange_trace:
            self.delegate_one('痕迹')


        self.set_next_run(task='Delegation', success=True, finish=True)
        raise TaskEnd

    def delegate_one(self, name: str) -> bool:
        """
        委派一个任务
        :param name:
        :return:
        """
        def ui_click(click, stop):
            while 1:
                self.screenshot()
                if self.appear(stop):
                    break
                if self.click(click, interval=1.5):
                    continue
        logger.hr('Delegation one', 2)
        self.O_D_NAME.keyword = name
        self.screenshot()
        if not self.ocr_appear(self.O_D_NAME):
            logger.warning(f'Delegation: {name} not found')
            return False
        enter_timer = Timer(15).start()
        while 1:
            self.screenshot()
            if self.appear(self.I_D_START):
                break
            if enter_timer.reached():
                logger.warning(f'Delegation: {name} enter timeout')
                return False

            # 检测到弹出的勾玉确认框，优先点击取消保护勾玉
            if self.appear_then_click(self.I_UI_CANCEL, interval=1):
                continue

            # 如果出现’召回‘ ’返回‘ 说明这个是现在委派中
            # 需要退出
            if self.appear(self.I_D_BACK):
                logger.warning(f'Delegation: {name} is in delegation')
                back_timer = Timer(6).start()
                while 1:
                    self.screenshot()
                    if not self.appear(self.I_D_BACK):
                        break
                    if back_timer.reached():
                        logger.warning('Exit delegation detail timeout')
                        break
                    # 若此时被取消弹窗遮挡返回，优先点取消
                    if self.appear_then_click(self.I_UI_CANCEL, interval=1):
                        continue
                    if self.appear_then_click(self.I_D_BACK, interval=1.2):
                        continue
                self.wait_until_appear(self.I_REWARDS_MIN, wait_time=3)
                return False
            if self.appear_then_click(self.I_D_SKIP, interval=0.8):
                continue
            if self.appear_then_click(self.I_D_CONFIRM, interval=0.8):
                continue
            # 点击委派任务名：防抖由 1s 提升至 3s，杜绝跨页面过渡时误触右上角"完成(30勾玉)"
            if self.ocr_appear_click(self.O_D_NAME, interval=3):
                continue
        # 进入委派  fefe e  fe
        logger.info(f'Enter Delegation: {name}')
        ui_click(self.C_D_1, self.I_D_SELECT_1)
        ui_click(self.C_D_2, self.I_D_SELECT_2)
        ui_click(self.C_D_3, self.I_D_SELECT_3)
        ui_click(self.C_D_4, self.I_D_SELECT_4)
        # 委派开始
        logger.info(f'Delegation: {name} start')
        start_timer = Timer(10).start()
        while 1:
            self.screenshot()
            if not self.appear(self.I_D_START):
                break
            if start_timer.reached():
                logger.warning(f'Delegation: {name} start timeout')
                break
            if self.click(self.C_D_5, interval=0.8):
                continue
            if self.appear_then_click(self.I_D_START, interval=1.8):
                continue
        # ui_click(self.C_D_5, self.I_D_SELECT_5)
        # self.ui_click_until_disappear(self.I_D_START)

    def check_reward(self):
        check_timer = Timer(3)
        check_timer.start()
        # 特殊委派（弥助的画、接送…）完成后会先播剧情：整屏压暗后地图右上角的 << 灯笼会被
        # REWARDS_CHAT 命中（实测 0.98），但结算面板还没出来，连点同一个按钮 10 次就会抛
        # GameTooManyClickError 打死整个任务。这里给返回键加连点上限，超限后按剧情处理：
        # 点对白区域推进剧情，整体再有硬超时兜底。
        story_timer = Timer(8)
        story_click = Timer(1).start()
        back_clicks = 0
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_REWARDS_GET, interval=1):
                back_clicks = 0
                story_timer.clear()
                check_timer.reset()
                continue
            if back_clicks < 3:
                if self.appear_then_click(self.I_REWARDS_CHAT, interval=1):
                    back_clicks += 1
                    check_timer.reset()
                    continue
            if self.appear_then_click(self.I_CHAT_1, interval=1):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_CHAT_2, interval=1):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_REWARDS_DONE, interval=1):
                back_clicks = 0
                story_timer.clear()
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_REWARDS_FALSE, interval=1):
                back_clicks = 0
                story_timer.clear()
                check_timer.reset()
                continue

            if back_clicks >= 3:
                # 返回键点了 3 次画面没变化 = 剧情浮层，点对白区域推进
                story_timer.start()
                if story_timer.reached():
                    logger.warning('Delegation: reward panel not found, story may stuck, skip')
                    return
                if story_click.reached_and_reset():
                    # control_check=False：同一坐标连点不进点击去重表，否则照样抛 GameTooManyClickError
                    self.device.click(640, 620, control_check=False)
                continue
            if not self.appear(self.I_REWARDS_MIN):
                continue
            if check_timer.reached():
                break
            # O_D_DONE 命中的是卡片上“完成”缎带，可点的领取位置在其正下方同样大小的一块
            if self.ocr_appear(self.O_D_DONE, interval=1):
                # 同一帧里可能有多张卡都显示“完成”，此时 Full 模式会把多个命中框合并成一个，
                # 合并框正下方不一定是可点的领取位置；这里取单个命中框，点它正下方同样大小的一块
                results = self.O_D_DONE.detect_and_ocr(self.device.image, logDisplay=False)
                index_list = self.O_D_DONE.filter(results, self.O_D_DONE.keyword) if results else None
                if index_list:
                    box = results[index_list[0]].box
                    x = box[0, 0] + self.O_D_DONE.roi[0]
                    y = box[0, 1] + self.O_D_DONE.roi[1]
                    w = box[1, 0] - box[0, 0]
                    h = box[2, 1] - box[0, 1]
                    self.device.click(x=x + w / 2, y=y + h + h / 2, control_name=self.O_D_DONE.name)
                check_timer.reset()
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    # t.delegate_one('弥助的画')
    t.run()



