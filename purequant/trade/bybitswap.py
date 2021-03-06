from purequant.config import config
from purequant.exceptions import *
import time
from purequant.exchange.bybit.bybit_swap import BybitSwap


class BYBITSWAP:

    def __init__(self, access_key, secret_key, instrument_id, margin_mode=None, leverage=None, testing=None):
        """
        bybit正向合约
        :param access_key: api key
        :param secret_key: api secret
        :param instrument_id: 合约id， e.g. "BTC-USDT"
        :param margin_mode: "fixed"逐仓，"crossed"全仓
        :param leverage: 如为逐仓模式，杠杆倍数需大于0，全仓模式杠杆为0
        :param testing: 是否为模拟账户
        """
        self.__symbol = instrument_id.split("-")[0] + instrument_id.split("-")[1]
        self.__bybit = BybitSwap(access_key, secret_key, testing=testing or False)
        self.__leverage = leverage or 20
        if margin_mode == "fixed":
            self.__bybit.set_leverage(self.__symbol, self.__leverage, self.__leverage)
        else:
            self.__bybit.set_leverage(self.__symbol, 0, 0)

    def get_depth(self, type=None):
        response = self.__bybit.get_orderbook(self.__symbol)
        if type == "asks":
            return response['asks']
        elif type == "bids":
            return response['bids']
        else:
            return response

    def get_position(self, mode=None):
        if mode == "both":
            long_amount = 0
            long_price = 0
            short_amount = 0
            short_price = 0
            result = self.__bybit.get_position(self.__symbol)['result']
            if result[0]['side'] == "Buy":
                long_amount = result[0]['size']
                long_price = result[0]['entry_price']
            if result[1]['side'] == "Sell":
                short_amount = result[1]['size']
                short_price = result[1]['entry_price']
            return {
                "long": {
                    "price": long_price,
                    "amount": long_amount
                },
                "short": {
                    "price": short_price,
                    "amount": short_amount
                }
            }
        else:
            result = self.__bybit.get_position(self.__symbol)['result']
            if result[0]['side'] == "Buy":
                return {'direction': "long", 'amount': result[0]['size'], 'price': result[0]['entry_price']}
            elif result[1]['side'] == "Sell":
                return {'direction': "short", 'amount': result[1]['size'], 'price': result[1]['entry_price']}

    def get_contract_value(self):
        """返回多少美元"""
        return self.get_ticker()['last']

    def get_kline(self, time_frame):
        return self.__bybit.get_kline(self.__symbol, time_frame)

    def get_ticker(self):
        response = self.__bybit.get_ticker(self.__symbol)
        receipt = {'symbol': self.__symbol, 'last': response['result'][0]['last_price']}
        return receipt

    def revoke_order(self, order_id):
        receipt = self.__bybit.cancel_order(self.__symbol, order_id)
        if receipt['ret_msg'] == "OK":
            return '【交易提醒】撤单成功'
        else:
            return '【交易提醒】撤单失败'

    def get_order_info(self, order_id):
        result = self.__bybit.get_realtime_order(self.__symbol, order_id)
        action = None
        if result['result']['side'] == "Buy" and result['result']['reduce_only'] == False:
            action = "买入开多"
        elif result['result']['side'] == "Sell" and result['result']['reduce_only'] == True:
            action = "卖出平多"
        elif result['result']['side'] == "Buy" and result['result']['reduce_only'] == True:
            action = "买入平空"
        elif result['result']['side'] == "Sell" and result['result']['reduce_only'] == False:
            action = "卖出开空"

        if result['result']['order_status'] == "Filled":
            dict = {"交易所": "BYBIT正向合约", "币对": self.__symbol, "方向": action, "订单状态": "完全成交",
                    "委托价格": result['result']['price'],
                    "已成交数量": float(result['result']['cum_exec_qty']),
                    "成交金额": result["result"]['cum_exec_value']}
            return dict
        elif result['result']['order_status'] == "Rejected":
            dict = {"交易所": "BYBIT正向合约", "币对": self.__symbol, "方向": action, "订单状态": "失败"}
            return dict
        elif result['result']['order_status'] == "Cancelled":
            dict = {"交易所": "BYBIT正向合约", "币对": self.__symbol, "方向": action, "订单状态": "撤单成功",
                    "委托价格": result['result']['price'],
                    "已成交数量": float(result['result']['cum_exec_qty']),
                    "成交金额": result["result"]['cum_exec_value']}
            return dict
        elif result['result']['order_status'] == "New":
            dict = {"交易所": "BYBIT正向合约", "币对": self.__symbol, "方向": action, "订单状态": "等待成交"}
            return dict
        elif result['result']['order_status'] == "PartiallyFilled":
            dict = {"交易所": "BYBIT正向合约", "币对": self.__symbol, "方向": action, "订单状态": "部分成交",
                    "委托价格": result['result']['price'],
                    "已成交数量": float(result['result']['cum_exec_qty']),
                    "成交金额": result["result"]['cum_exec_value']}
            return dict
        elif result['result']['order_status'] == "Created ":
            dict = {"交易所": "BYBIT正向合约", "币对": self.__symbol, "方向": action, "订单状态": "等待成交"}
            return dict

    def buy(self, price, size, order_type=None, time_in_force=None):
        if config.backtest is False:  # 实盘模式
            order_type = order_type or "Limit"
            time_in_force = time_in_force or "GoodTillCancel"
            result = self.__bybit.create_order(symbol=self.__symbol, side="Buy", price=price, qty=size, order_type=order_type, time_in_force=time_in_force,
                                               reduce_only=False, close_on_trigger=False)
            if result['ret_msg'] != "OK":  # 如果下单失败就抛出异常，提示错误信息。
                raise SendOrderError(result['ret_msg'])
            order_info = self.get_order_info(order_id=result['result']['order_id'])  # 下单后查询一次订单状态
            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":  # 如果订单状态为"完全成交"或者"失败"，返回结果
                return {"【交易提醒】下单结果": order_info}
            # 如果订单状态不是"完全成交"或者"失败"
            if config.price_cancellation:  # 选择了价格撤单时，如果最新价超过委托价一定幅度，撤单重发，返回下单结果
                if order_info["订单状态"] == "等待成交":
                    if float(self.get_ticker()['last']) >= price * (1 + config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.buy(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                                size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    if float(self.get_ticker()['last']) >= price * (1 + config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.buy(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                                size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
            if config.time_cancellation:  # 选择了时间撤单时，如果委托单发出多少秒后不成交，撤单重发，直至完全成交，返回成交结果
                time.sleep(config.time_cancellation_seconds)
                order_info = self.get_order_info(order_id=result['result']['order_id'])
                if order_info["订单状态"] == "等待成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.buy(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                            size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.buy(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                            size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
            if config.automatic_cancellation:
                # 如果订单未完全成交，且未设置价格撤单和时间撤单，且设置了自动撤单，就自动撤单并返回下单结果与撤单结果
                try:
                    self.revoke_order(order_id=result['result']['order_id'])
                    state = self.get_order_info(order_id=result['result']['order_id'])
                    return {"【交易提醒】下单结果": state}
                except:
                    order_info = self.get_order_info(order_id=result['result']['order_id'])
                    if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                        return {"【交易提醒】下单结果": order_info}
            else:  # 未启用交易助手时，下单并查询订单状态后直接返回下单结果
                return {"【交易提醒】下单结果": order_info}
        else:  # 回测模式
            return "回测模拟下单成功！"

    def buytocover(self, price, size, order_type=None, time_in_force=None):
        if config.backtest is False:  # 实盘模式
            order_type = order_type or "Limit"
            time_in_force = time_in_force or "GoodTillCancel"
            result = self.__bybit.create_order(symbol=self.__symbol, side="Buy", price=price, qty=size,
                                               order_type=order_type, time_in_force=time_in_force,
                                               reduce_only=True, close_on_trigger=True)
            if result['ret_msg'] != "OK":  # 如果下单失败就抛出异常，提示错误信息。
                raise SendOrderError(result['ret_msg'])
            order_info = self.get_order_info(order_id=result['result']['order_id'])  # 下单后查询一次订单状态
            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":  # 如果订单状态为"完全成交"或者"失败"，返回结果
                return {"【交易提醒】下单结果": order_info}
            # 如果订单状态不是"完全成交"或者"失败"
            if config.price_cancellation:  # 选择了价格撤单时，如果最新价超过委托价一定幅度，撤单重发，返回下单结果
                if order_info["订单状态"] == "等待成交":
                    if float(self.get_ticker()['last']) >= price * (1 + config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.buytocover(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                                size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    if float(self.get_ticker()['last']) >= price * (1 + config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.buytocover(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                                size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
            if config.time_cancellation:  # 选择了时间撤单时，如果委托单发出多少秒后不成交，撤单重发，直至完全成交，返回成交结果
                time.sleep(config.time_cancellation_seconds)
                order_info = self.get_order_info(order_id=result['result']['order_id'])
                if order_info["订单状态"] == "等待成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.buytocover(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                            size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.buytocover(float(self.get_ticker()['last']) * (1 + config.reissue_order),
                                            size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
            if config.automatic_cancellation:
                # 如果订单未完全成交，且未设置价格撤单和时间撤单，且设置了自动撤单，就自动撤单并返回下单结果与撤单结果
                try:
                    self.revoke_order(order_id=result['result']['order_id'])
                    state = self.get_order_info(order_id=result['result']['order_id'])
                    return {"【交易提醒】下单结果": state}
                except:
                    order_info = self.get_order_info(order_id=result['result']['order_id'])
                    if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                        return {"【交易提醒】下单结果": order_info}
            else:  # 未启用交易助手时，下单并查询订单状态后直接返回下单结果
                return {"【交易提醒】下单结果": order_info}
        else:  # 回测模式
            return "回测模拟下单成功！"

    def sell(self, price, size, order_type=None, time_in_force=None):
        if config.backtest is False:  # 实盘模式
            order_type = order_type or "Limit"
            time_in_force = time_in_force or "GoodTillCancel"
            result = self.__bybit.create_order(symbol=self.__symbol, side="Sell", price=price, qty=size, order_type=order_type, time_in_force=time_in_force,
                                               reduce_only=True, close_on_trigger=True)
            if result['ret_msg'] != "OK":  # 如果下单失败就抛出异常，提示错误信息。
                raise SendOrderError(result['ret_msg'])
            order_info = self.get_order_info(order_id=result['result']['order_id'])  # 下单后查询一次订单状态
            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":  # 如果订单状态为"完全成交"或者"失败"，返回结果
                return {"【交易提醒】下单结果": order_info}
            # 如果订单状态不是"完全成交"或者"失败"
            if config.price_cancellation:  # 选择了价格撤单时，如果最新价超过委托价一定幅度，撤单重发，返回下单结果
                if order_info["订单状态"] == "等待成交":
                    if float(self.get_ticker()['last']) <= price * (1 - config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.sell(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                                size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    if float(self.get_ticker()['last']) <= price * (1 - config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.sell(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                                size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
            if config.time_cancellation:  # 选择了时间撤单时，如果委托单发出多少秒后不成交，撤单重发，直至完全成交，返回成交结果
                time.sleep(config.time_cancellation_seconds)
                order_info = self.get_order_info(order_id=result['result']['order_id'])
                if order_info["订单状态"] == "等待成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.sell(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                            size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.sell(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                            size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
            if config.automatic_cancellation:
                # 如果订单未完全成交，且未设置价格撤单和时间撤单，且设置了自动撤单，就自动撤单并返回下单结果与撤单结果
                try:
                    self.revoke_order(order_id=result['result']['order_id'])
                    state = self.get_order_info(order_id=result['result']['order_id'])
                    return {"【交易提醒】下单结果": state}
                except:
                    order_info = self.get_order_info(order_id=result['result']['order_id'])
                    if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                        return {"【交易提醒】下单结果": order_info}
            else:  # 未启用交易助手时，下单并查询订单状态后直接返回下单结果
                return {"【交易提醒】下单结果": order_info}
        else:  # 回测模式
            return "回测模拟下单成功！"

    def sellshort(self, price, size, order_type=None, time_in_force=None):
        if config.backtest is False:  # 实盘模式
            order_type = order_type or "Limit"
            time_in_force = time_in_force or "GoodTillCancel"
            result = self.__bybit.create_order(symbol=self.__symbol, side="Sell", price=price, qty=size,
                                               order_type=order_type, time_in_force=time_in_force,
                                               reduce_only=False, close_on_trigger=False)
            if result['ret_msg'] != "OK":  # 如果下单失败就抛出异常，提示错误信息。
                raise SendOrderError(result['ret_msg'])
            order_info = self.get_order_info(order_id=result['result']['order_id'])  # 下单后查询一次订单状态
            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":  # 如果订单状态为"完全成交"或者"失败"，返回结果
                return {"【交易提醒】下单结果": order_info}
            # 如果订单状态不是"完全成交"或者"失败"
            if config.price_cancellation:  # 选择了价格撤单时，如果最新价超过委托价一定幅度，撤单重发，返回下单结果
                if order_info["订单状态"] == "等待成交":
                    if float(self.get_ticker()['last']) <= price * (1 - config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.sellshort(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                                 size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    if float(self.get_ticker()['last']) <= price * (1 - config.price_cancellation_amplitude):
                        try:
                            self.revoke_order(order_id=result['result']['order_id'])
                            state = self.get_order_info(order_id=result['result']['order_id'])
                            if state['订单状态'] == "撤单成功":
                                return self.sellshort(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                                 size - state["已成交数量"])
                        except:
                            order_info = self.get_order_info(order_id=result['result']['order_id'])
                            if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                                return {"【交易提醒】下单结果": order_info}
            if config.time_cancellation:  # 选择了时间撤单时，如果委托单发出多少秒后不成交，撤单重发，直至完全成交，返回成交结果
                time.sleep(config.time_cancellation_seconds)
                order_info = self.get_order_info(order_id=result['result']['order_id'])
                if order_info["订单状态"] == "等待成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.sellshort(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                             size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
                if order_info["订单状态"] == "部分成交":
                    try:
                        self.revoke_order(order_id=result['result']['order_id'])
                        state = self.get_order_info(order_id=result['result']['order_id'])
                        if state['订单状态'] == "撤单成功":
                            return self.sellshort(float(self.get_ticker()['last']) * (1 - config.reissue_order),
                                             size - state["已成交数量"])
                    except:
                        order_info = self.get_order_info(order_id=result['result']['order_id'])
                        if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                            return {"【交易提醒】下单结果": order_info}
            if config.automatic_cancellation:
                # 如果订单未完全成交，且未设置价格撤单和时间撤单，且设置了自动撤单，就自动撤单并返回下单结果与撤单结果
                try:
                    self.revoke_order(order_id=result['result']['order_id'])
                    state = self.get_order_info(order_id=result['result']['order_id'])
                    return {"【交易提醒】下单结果": state}
                except:
                    order_info = self.get_order_info(order_id=result['result']['order_id'])
                    if order_info["订单状态"] == "完全成交" or order_info["订单状态"] == "失败 ":
                        return {"【交易提醒】下单结果": order_info}
            else:  # 未启用交易助手时，下单并查询订单状态后直接返回下单结果
                return {"【交易提醒】下单结果": order_info}
        else:  # 回测模式
            return "回测模拟下单成功！"

    def BUY(self, cover_short_price, cover_short_size, open_long_price, open_long_size, order_type=None, time_in_force=None):
        if config.backtest is False:  # 实盘模式
            result1 = self.buytocover(cover_short_price, cover_short_size, order_type, time_in_force)
            if "完全成交" in str(result1):
                result2 = self.buy(open_long_price, open_long_size, order_type, time_in_force)
                return {"平仓结果": result1, "开仓结果": result2}
            else:
                return result1
        else:  # 回测模式
            return "回测模拟下单成功！"

    def SELL(self, cover_long_price, cover_long_size, open_short_price, open_short_size, order_type=None, time_in_force=None):
        if config.backtest is False:  # 实盘模式
            result1 = self.sell(cover_long_price, cover_long_size, order_type, time_in_force)
            if "完全成交" in str(result1):
                result2 = self.sellshort(open_short_price, open_short_size, order_type, time_in_force)
                return {"平仓结果": result1, "开仓结果": result2}
            else:
                return result1
        else:  # 回测模式
            return "回测模拟下单成功！"