# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import onepush.core
import yaml
from onepush import get_notifier
from onepush.core import Provider
from onepush.exceptions import OnePushException
from onepush.providers.custom import Custom
from requests import Response
from smtplib import SMTPResponseException

from module.logger import logger
onepush.core.log = logger


class Notifier:
    def __init__(self, _config: str, enable: bool=False) -> None:
        self.config_name: str = ""
        self.enable: bool = enable
        # [YYS-sc3-patch] ???provider ??????????????? push() ? AttributeError
        self.notifier = None
        self.required = []

        if not self.enable:
            return
        config = {}
        try:
            for item in yaml.safe_load_all(_config):
                config.update(item)
        except Exception as e:
            logger.error("Fail to load onepush config, skip sending")
            return
        self.config = config
        try:
            # 获取provider
            self.provider_name: str = self.config.pop("provider", None)
            if self.provider_name is None:
                logger.info("No provider specified, skip sending")
                return
            # 获取notifier
            # [YYS-sc3-patch] Server?3 ?????onepush 1.3.0 ??? sctp key???????
            if self.provider_name.lower() == 'serverchan3':
                self.required = ['sc3key', 'title']
                return
            self.notifier: Provider = get_notifier(self.provider_name)
            # 获取notifier的必填参数
            self.required: list[str] = self.notifier.params["required"]
        except OnePushException:
            logger.exception("Init notifier failed")
            return
        except Exception as e:
            logger.exception(e)
            return

    def push(self, **kwargs) -> bool:
        if not self.enable:
            return False
        # 更新配置
        kwargs["title"] = f"{self.config_name} {kwargs['title']}"
        self.config.update(kwargs)

        # [YYS-sc3-patch] Server?3 ??????
        if self.provider_name and self.provider_name.lower() == 'serverchan3':
            return self._push_serverchan3(kwargs)
        # pre check
        for key in self.required:
            if key not in self.config:
                logger.warning(
                    f"Notifier {self.notifier} require param '{key}' but not provided"
                )


        if isinstance(self.notifier, Custom):
            if "method" not in self.config or self.config["method"] == "post":
                self.config["datatype"] = "json"
            if not ("data" in self.config or isinstance(self.config["data"], dict)):
                self.config["data"] = {}
            if "title" in kwargs:
                self.config["data"]["title"] = kwargs["title"]
            if "content" in kwargs:
                self.config["data"]["content"] = kwargs["content"]

        if self.provider_name.lower() == "gocqhttp":
            access_token = self.config.get("access_token")
            if access_token:
                self.config["token"] = access_token


        try:
            resp = self.notifier.notify(**self.config)
            if isinstance(resp, Response):
                if resp.status_code != 200:
                    logger.warning("Push notify failed!")
                    logger.warning(f"HTTP Code:{resp.status_code}")
                    return False
                else:
                    if self.provider_name.lower() == "gocqhttp":
                        return_data: dict = resp.json()
                        if return_data["status"] == "failed":
                            logger.warning("Push notify failed!")
                            logger.warning(
                                f"Return message:{return_data['wording']}")
                            return False
        except SMTPResponseException:
            logger.warning("Appear SMTPResponseException")
            pass
        except OnePushException:
            logger.exception("Push notify failed")
            return False
        except Exception as e:
            logger.exception(e)
            return False

        logger.info("Push notify success")
        return True

    # [YYS-sc3-patch] Server?3?Server?????????
    # ?????script.error.notify_config??? YAML??
    #   {provider: serverchan3, sc3key: sctpXXXXXXXX, tags: OAS|??}
    def _push_serverchan3(self, kwargs) -> bool:
        import json as _json
        import requests as _requests

        sc3key = self.config.get('sc3key')
        if not sc3key:
            logger.warning("Notifier serverchan3 require param 'sc3key' but not provided")
            return False
        url = 'https://' + sc3key + '.push.ft07.com/send'
        payload = {
            'title': kwargs.get('title', ''),
            'desp': kwargs.get('content', ''),
        }
        if self.config.get('tags'):
            payload['tags'] = self.config['tags']
        if self.config.get('short'):
            payload['short'] = self.config['short']
        headers = {
            'Content-Type': 'application/json;charset=utf-8',
            # ???????? python-urllib ??? UA ?? 403???????? UA
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        }
        try:
            resp = _requests.post(url,
                                  data=_json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                  headers=headers, timeout=20)
            if resp.status_code != 200:
                logger.warning('Push notify failed!')
                logger.warning('HTTP Code: ' + str(resp.status_code) + ' ' + resp.text[:200])
                return False
            ret = resp.json()
            if int(ret.get('code', -1)) != 0:
                logger.warning('Push notify failed!')
                logger.warning('Return message: ' + str(ret.get('message')))
                return False
        except Exception as e:
            logger.exception(e)
            return False
        logger.info('Push notify success')
        return True
