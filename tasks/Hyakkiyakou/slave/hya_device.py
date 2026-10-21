import timeit
import numpy as np
from datetime import datetime

from module.base.timer import Timer
from module.logger import logger
from module.base.utils import point2str
from module.exception import RequestHumanTakeover, GameStuckError
from tasks.base_task import BaseTask

from tasks.Hyakkiyakou.config import ScreenshotMethod, ControlMethod
from module.device.env import IS_WINDOWS

def image_black(img) -> bool:
    for y, x in [(0, 0), (719, 1279), (719, 0), (0, 1279)]:
        if np.all(img[y, x] != 0):
            return False
    return True


class HyaDevice(BaseTask):
    """
    这个类主要是是优化截屏点击速度
    1. 使用特别的method
    2. 扔掉中间的冗余校验
    3. 考虑JIT加速
    我宣布世界上最好的 Linux 系统是 Windows
    """
    hya_screenshot_interval = Timer(0.2)  # 300ms
    hya_fs_check_timer = Timer(3 * 60)  # 五分钟跑不完就应该是出问题了

    def fast_screenshot(self, screenshot: ScreenshotMethod):
        self.hya_screenshot_interval.wait()
        self.hya_screenshot_interval.reset()
        # YYS-linux-hya-patch: window_background / nemu_ipc 只在 Windows(MuMu) 上存在，
        # Linux(redroid) 回落到实例自己的截图方式（实测 DroidCast_raw ~25ms）。
        if IS_WINDOWS and screenshot == ScreenshotMethod.WINDOW_BACKGROUND:
            self.device.image = self.device.screenshot_window_background()
        elif IS_WINDOWS and screenshot == ScreenshotMethod.NEMU_IPC:
            self.device.image = self.device.screenshot_nemu_ipc()
        else:
            # Device.screenshot() 会跑 stuck_record_check()（60s 看门狗），而撒豆的 fast_click
            # 用 control_check=False 绕过了 handle_control_check()，看门狗永不被重置
            # -> 每场战斗满 60s 必报 GameStuckError。上游 direct 调方法就是为避开它，这里照做。
            shot = self.device.screenshot_methods.get(self.config.script.device.screenshot_method)
            self.device.image = (shot or self.device.screenshot_adb)()
        if image_black(self.device.image):
            logger.error('Screenshot image is black, try again')
            raise RequestHumanTakeover('Screenshot image is black, try again')
        if self.hya_fs_check_timer.reached():
            logger.error('Fast screenshot check timer reached')
            logger.error('Five minutes have not ended, the game is probably stuck, please check the game')
            raise GameStuckError
        if self.config.script.error.save_error:
            self.device.screenshot_deque.append({'time': datetime.now(), 'image': self.device.image})
        return self.device.image

    def fast_click(self, x: int, y: int, control_method: ControlMethod = ControlMethod.WINDOW_MESSAGE) -> None:
        logger.info(
            'Click %s @ %s' % (point2str(x, y), 'Click')
        )
        # YYS-linux-hya-patch: window_message 仅 Windows；minitouch 要 /dev/input，redroid 没有。
        if IS_WINDOWS and control_method == ControlMethod.MINITOUCH:
            self.device.click_minitouch(x=x, y=y)
        elif IS_WINDOWS and control_method == ControlMethod.WINDOW_MESSAGE:
            self.device.click_window_message(x=x, y=y, fast=True)
        else:
            self.device.click(x, y, control_check=False, control_name='HyaClick')

    def set_fast_screenshot_interval(self, interval: float):
        """

        @param interval: ms
        @return:
        """
        self.hya_screenshot_interval = Timer(interval / 1000.)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaDevice(c, d)

    # def screenshot():
    #     global hd
    #     # hd.fast_screenshot()
    #     hd.fast_click(420, 370)
    #     hd.fast_click(750, 400)
    # execution_time = timeit.timeit(screenshot, number=50)
    # print(f"执行总的时间: {execution_time * 1000} ms")

    hd.fast_screenshot()

