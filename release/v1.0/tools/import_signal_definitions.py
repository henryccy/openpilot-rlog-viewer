# -*- coding: utf-8 -*-
"""
訊號定義匯入工具
Import Signal Definitions Tool

功能：
1. 解析 log.capnp 取得所有 Cereal 訊號定義
2. 解析 DBC 檔案取得所有 CAN 訊號定義
3. 加上中文註解
4. 匯入到資料庫
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import capnp
import re
from pathlib import Path
from typing import List, Dict, Tuple
import logging

from src.core.database import DatabaseManager
from src.core.dbc_parser import DBCParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 導入單位定義
try:
    from extract_cereal_units import CEREAL_SIGNAL_UNITS, UNIT_CN_MAP
except ImportError:
    # 如果找不到檔案，定義一個空字典
    CEREAL_SIGNAL_UNITS = {}
    UNIT_CN_MAP = {}


class SignalDefinitionImporter:
    """訊號定義匯入器"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

        # Cereal 訊號中文對照
        self.cereal_translations = {
            # carState
            'vEgo': '車速',
            'aEgo': '加速度',
            'vEgoRaw': '原始車速',
            'vEgoCluster': '儀表板車速',
            'yawRate': '偏航率',
            'steeringAngleDeg': '方向盤角度',
            'steeringAngleOffsetDeg': '方向盤角度偏移',
            'steeringRateDeg': '方向盤轉速',
            'steeringTorque': '方向盤扭矩',
            'steeringPressed': '方向盤已按壓',
            'steeringRateLimited': '方向盤轉速受限',
            'gas': '油門開度',
            'gasPressed': '油門已踩下',
            'brake': '煞車壓力',
            'brakePressed': '煞車已踩下',
            'brakeHoldActive': '煞車保持啟用',
            'parkingBrake': '手煞車',
            'brakeLights': '煞車燈',
            'leftBlinker': '左轉向燈',
            'rightBlinker': '右轉向燈',
            'genericToggle': '通用開關',
            'doorOpen': '車門已開',
            'seatbeltUnlatched': '安全帶未繫',
            'gearShifter': '檔位',
            'wheelSpeeds': '車輪速度',
            'cruiseState': '定速巡航狀態',
            'buttonEvents': '按鈕事件',

            # controlsState
            'enabled': '已啟用',
            'active': '作用中',
            'longControlState': '縱向控制狀態',
            'vPid': 'PID速度',
            'vTargetLead': '前車目標速度',
            'vCruise': '巡航速度',
            'upAccelCmd': '上升加速命令',
            'uiAccelCmd': 'UI加速命令',
            'aTarget': '目標加速度',
            'curvature': '曲率',

            # carControl
            'actuators': '執行器',
            'hudControl': 'HUD控制',
            'cruiseControl': '巡航控制',

            # liveParameters
            'valid': '有效',
            'posenetValid': 'Posenet有效',
            'sensorValid': '感測器有效',
            'steerRatio': '轉向比',
            'stiffnessFactor': '剛度係數',
            'angleOffsetAverageDeg': '平均角度偏移',
            'angleOffsetDeg': '角度偏移',

            # radarState
            'leadOne': '前車1',
            'leadTwo': '前車2',
            'dRel': '相對距離',
            'yRel': '相對橫向位置',
            'vRel': '相對速度',
            'aRel': '相對加速度',
            'status': '狀態',
            'fcw': '前方碰撞警告',

            # longitudinalPlan
            'accels': '加速度陣列',
            'speeds': '速度陣列',
            'jerks': '躍度陣列',
            'hasLead': '有前車',
            'longitudinalPlanSource': '縱向計劃來源',
            'fcw': '前方碰撞警告',
            'processingDelay': '處理延遲',
            'solverExecutionTime': '求解執行時間',

            # lateralPlan
            'laneWidth': '車道寬度',
            'dPathPoints': '路徑點',
            'psis': '偏航角陣列',
            'curvatures': '曲率陣列',
            'curvatureRates': '曲率變化率陣列',
            'mpcSolutionValid': 'MPC解有效',
            'desire': '駕駛意圖',
            'laneChangeState': '換道狀態',
            'laneChangeDirection': '換道方向',
        }

        # 訊號分類對照
        self.cereal_categories = {
            'carState': 'vehicle_state',
            'carControl': 'control',
            'controlsState': 'control',
            'carParams': 'vehicle_state',
            'liveParameters': 'control',
            'radarState': 'sensor',
            'longitudinalPlan': 'control',
            'lateralPlan': 'control',
            'liveCalibration': 'sensor',
            'liveTracks': 'sensor',
            'model': 'model',
            'modelV2': 'model',
            'drivingModelData': 'model',
            'plan': 'control',
            'gpsLocation': 'navigation',
            'gpsLocationExternal': 'navigation',
            'liveLocationKalman': 'navigation',
            'livePose': 'navigation',
        }

    def import_cereal_signals(self, capnp_path: str = 'log.capnp') -> int:
        """
        匯入 Cereal 訊號定義 - 動態解析所有訊號類型和欄位

        Args:
            capnp_path: log.capnp 檔案路徑

        Returns:
            匯入的訊號數量
        """
        logger.info(f"開始匯入 Cereal 訊號定義從 {capnp_path}")

        # 刪除所有舊的 Cereal 訊號定義
        logger.info("刪除舊的 Cereal 訊號定義...")
        try:
            self.db_manager.cursor.execute("DELETE FROM cereal_signal_definitions")
            self.db_manager.conn.commit()
            logger.info("已清空舊的訊號定義")
        except Exception as e:
            logger.error(f"刪除舊定義失敗: {e}")
            self.db_manager.conn.rollback()

        try:
            # 載入所有 capnp 檔案
            capnp_log = capnp.load(capnp_path)
            car_capnp = capnp.load('car.capnp')
        except Exception as e:
            logger.error(f"無法載入 capnp 檔案: {e}")
            return 0

        imported_count = 0

        # 取得 Event union 中的所有訊號類型
        event_schema = capnp_log.Event.schema
        union_fields = event_schema.union_fields

        logger.info(f"找到 {len(union_fields)} 個 Event union 欄位")

        # 遍歷所有訊號類型
        for msg_type in union_fields:
            # 跳過不需要的類型（不跳過 DEPRECATED，因為實際資料中仍會記錄）
            if msg_type in ['initData', 'can', 'sendcan', 'logMessage', 'androidLog']:
                continue

            try:
                # 取得訊號類型的 schema
                # 嘗試從不同的 capnp 檔案中取得
                msg_schema = None

                # 首先嘗試從 log.capnp
                try:
                    msg_class_name = msg_type[0].upper() + msg_type[1:]
                    msg_class = getattr(capnp_log, msg_class_name)
                    msg_schema = msg_class.schema
                except:
                    pass

                # 如果找不到，嘗試從 car.capnp
                if msg_schema is None:
                    try:
                        msg_class = getattr(car_capnp, msg_class_name)
                        msg_schema = msg_class.schema
                    except:
                        logger.debug(f"無法取得 {msg_type} 的 schema")
                        continue

                # 取得所有欄位
                fields = msg_schema.non_union_fields

                category = self.cereal_categories.get(msg_type, 'sensor')

                # 處理每個欄位
                for field_name in fields:
                    # 不跳過 DEPRECATED 欄位（實際資料中仍會記錄）
                    # if 'DEPRECATED' in field_name:
                    #     continue

                    full_signal_name = f"{msg_type}.{field_name}"
                    name_cn = self.cereal_translations.get(field_name, '')

                    # 簡單的中文描述
                    description_cn = f"{msg_type} 的 {field_name} 欄位"
                    if name_cn:
                        description_cn = name_cn

                    # 取得欄位的資料類型
                    data_type = 'Unknown'
                    is_numeric = False
                    try:
                        field_proto = msg_schema.fields[field_name].proto
                        type_enum = field_proto.slot.type.which()

                        # 將 Cap'n Proto 型別轉換為可讀字串
                        if type_enum == 'void':
                            data_type = 'Void'
                        elif type_enum == 'bool':
                            data_type = 'Bool'
                        elif type_enum == 'int8':
                            data_type = 'Int8'
                            is_numeric = True
                        elif type_enum == 'int16':
                            data_type = 'Int16'
                            is_numeric = True
                        elif type_enum == 'int32':
                            data_type = 'Int32'
                            is_numeric = True
                        elif type_enum == 'int64':
                            data_type = 'Int64'
                            is_numeric = True
                        elif type_enum == 'uint8':
                            data_type = 'UInt8'
                            is_numeric = True
                        elif type_enum == 'uint16':
                            data_type = 'UInt16'
                            is_numeric = True
                        elif type_enum == 'uint32':
                            data_type = 'UInt32'
                            is_numeric = True
                        elif type_enum == 'uint64':
                            data_type = 'UInt64'
                            is_numeric = True
                        elif type_enum == 'float32':
                            data_type = 'Float32'
                            is_numeric = True
                        elif type_enum == 'float64':
                            data_type = 'Float64'
                            is_numeric = True
                        elif type_enum == 'text':
                            data_type = 'Text'
                        elif type_enum == 'data':
                            data_type = 'Data'
                        elif type_enum == 'list':
                            data_type = 'List'
                        elif type_enum == 'enum':
                            data_type = 'Enum'
                        elif type_enum == 'struct':
                            data_type = 'Struct'
                        elif type_enum == 'interface':
                            data_type = 'Interface'
                        elif type_enum == 'anyPointer':
                            data_type = 'AnyPointer'
                    except Exception as e:
                        logger.debug(f"無法取得 {full_signal_name} 的型別: {e}")

                    # 取得單位資訊
                    unit = CEREAL_SIGNAL_UNITS.get(field_name, '')
                    unit_cn = UNIT_CN_MAP.get(unit, '') if unit else ''

                    # 插入到資料庫
                    try:
                        self.db_manager.cursor.execute("""
                            INSERT INTO cereal_signal_definitions
                            (message_type, field_name, full_signal_name, data_type,
                             name_cn, description_cn, unit, unit_cn, category, is_numeric)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (full_signal_name)
                            DO UPDATE SET
                                name_cn = EXCLUDED.name_cn,
                                description_cn = EXCLUDED.description_cn,
                                data_type = EXCLUDED.data_type,
                                is_numeric = EXCLUDED.is_numeric,
                                unit = EXCLUDED.unit,
                                unit_cn = EXCLUDED.unit_cn,
                                category = EXCLUDED.category,
                                updated_at = CURRENT_TIMESTAMP
                        """, (msg_type, field_name, full_signal_name, data_type,
                              name_cn, description_cn, unit, unit_cn, category, is_numeric))

                        imported_count += 1
                        # 每次插入成功後立即 commit，避免單個失敗影響其他插入
                        self.db_manager.conn.commit()

                    except Exception as e:
                        logger.error(f"插入訊號失敗 {full_signal_name}: {e}")
                        # 回滾這個失敗的交易
                        self.db_manager.conn.rollback()

            except Exception as e:
                logger.warning(f"處理訊號類型 {msg_type} 時出錯: {e}")
                continue

        logger.info(f"成功匯入 {imported_count} 個 Cereal 訊號定義")
        return imported_count

    def _get_message_fields(self, msg_type: str) -> Dict[str, Dict]:
        """
        取得訊息類型的欄位定義

        這裡手動定義主要欄位，實際應該從 capnp schema 自動提取
        """
        # 定義主要訊號類型的欄位
        field_definitions = {
            'carState': {
                'vEgo': {'type': 'Float32', 'unit': 'm/s', 'unit_cn': '公尺/秒', 'description': '車輛速度'},
                'aEgo': {'type': 'Float32', 'unit': 'm/s²', 'unit_cn': '公尺/秒²', 'description': '車輛加速度'},
                'vEgoRaw': {'type': 'Float32', 'unit': 'm/s', 'unit_cn': '公尺/秒', 'description': '原始車速'},
                'vEgoCluster': {'type': 'Float32', 'unit': 'm/s', 'unit_cn': '公尺/秒', 'description': '儀表板車速'},
                'yawRate': {'type': 'Float32', 'unit': 'rad/s', 'unit_cn': '弧度/秒', 'description': '偏航率'},
                'steeringAngleDeg': {'type': 'Float32', 'unit': 'deg', 'unit_cn': '度', 'description': '方向盤角度'},
                'steeringRateDeg': {'type': 'Float32', 'unit': 'deg/s', 'unit_cn': '度/秒', 'description': '方向盤轉速'},
                'steeringTorque': {'type': 'Float32', 'unit': 'Nm', 'unit_cn': '牛頓·公尺', 'description': '方向盤扭矩'},
                'steeringPressed': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '方向盤已按壓'},
                'gas': {'type': 'Float32', 'unit': '', 'unit_cn': '', 'description': '油門開度 (0-1)'},
                'gasPressed': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '油門已踩下'},
                'brake': {'type': 'Float32', 'unit': '', 'unit_cn': '', 'description': '煞車壓力 (0-1)'},
                'brakePressed': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '煞車已踩下'},
                'leftBlinker': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '左轉向燈'},
                'rightBlinker': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '右轉向燈'},
            },
            'controlsState': {
                'enabled': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': 'openpilot 已啟用'},
                'active': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': 'openpilot 作用中'},
                'vEgo': {'type': 'Float32', 'unit': 'm/s', 'unit_cn': '公尺/秒', 'description': '當前車速'},
                'vEgoRaw': {'type': 'Float32', 'unit': 'm/s', 'unit_cn': '公尺/秒', 'description': '原始車速'},
                'vCruise': {'type': 'Float32', 'unit': 'kph', 'unit_cn': '公里/小時', 'description': '巡航設定速度'},
                'aTarget': {'type': 'Float32', 'unit': 'm/s²', 'unit_cn': '公尺/秒²', 'description': '目標加速度'},
                'curvature': {'type': 'Float32', 'unit': '1/m', 'unit_cn': '1/公尺', 'description': '道路曲率'},
            },
            'radarState': {
                'leadOne': {'type': 'Object', 'unit': '', 'unit_cn': '', 'description': '第一前車'},
                'leadTwo': {'type': 'Object', 'unit': '', 'unit_cn': '', 'description': '第二前車'},
            },
            'liveParameters': {
                'steerRatio': {'type': 'Float32', 'unit': '', 'unit_cn': '', 'description': '轉向比'},
                'stiffnessFactor': {'type': 'Float32', 'unit': '', 'unit_cn': '', 'description': '剛度係數'},
                'angleOffsetDeg': {'type': 'Float32', 'unit': 'deg', 'unit_cn': '度', 'description': '角度偏移'},
                'valid': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '參數有效'},
            },
            'longitudinalPlan': {
                'vCruise': {'type': 'Float32', 'unit': 'm/s', 'unit_cn': '公尺/秒', 'description': '巡航速度'},
                'aTarget': {'type': 'Float32', 'unit': 'm/s²', 'unit_cn': '公尺/秒²', 'description': '目標加速度'},
                'hasLead': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '有前車'},
                'fcw': {'type': 'Bool', 'unit': '', 'unit_cn': '', 'description': '前方碰撞警告'},
            },
            'lateralPlan': {
                'laneWidth': {'type': 'Float32', 'unit': 'm', 'unit_cn': '公尺', 'description': '車道寬度'},
                'dPathPoints': {'type': 'List', 'unit': '', 'unit_cn': '', 'description': '路徑點'},
                'desire': {'type': 'Enum', 'unit': '', 'unit_cn': '', 'description': '駕駛意圖'},
                'laneChangeState': {'type': 'Enum', 'unit': '', 'unit_cn': '', 'description': '換道狀態'},
            },
        }

        return field_definitions.get(msg_type, {})

    def import_can_signals(self, dbc_path: str = 'vw_mqb.dbc') -> int:
        """
        匯入 CAN 訊號定義

        Args:
            dbc_path: DBC 檔案路徑

        Returns:
            匯入的訊號數量
        """
        logger.info(f"開始匯入 CAN 訊號定義從 {dbc_path}")

        try:
            dbc_parser = DBCParser(dbc_path)
        except Exception as e:
            logger.error(f"無法載入 DBC: {e}")
            return 0

        imported_count = 0

        # 遍歷所有訊息
        for msg in dbc_parser.db.messages:
            can_id = msg.frame_id
            can_id_hex = f"0x{can_id:03X}"
            message_name = msg.name
            message_name_cn = dbc_parser.translate_to_chinese(msg.name)

            # 遍歷訊息中的所有訊號
            for signal in msg.signals:
                signal_name = signal.name
                full_signal_name = f"CAN_{can_id_hex}_{signal_name}"

                # 中文翻譯
                signal_name_cn = dbc_parser.translate_to_chinese(signal_name)
                description_cn = dbc_parser.translate_to_chinese(signal.comment) if signal.comment else signal_name_cn

                # 單位
                unit = signal.unit if signal.unit else ''
                unit_cn = dbc_parser.translate_to_chinese(unit) if unit else ''

                # 訊號屬性
                try:
                    self.db_manager.cursor.execute("""
                        INSERT INTO can_signal_definitions
                        (can_id, can_id_hex, signal_name, full_signal_name,
                         message_name, message_name_cn,
                         start_bit, bit_length, byte_order, is_signed,
                         scale, "offset", min_value, max_value,
                         signal_name_cn, description_cn, unit, unit_cn,
                         comment, category)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (full_signal_name)
                        DO UPDATE SET
                            message_name_cn = EXCLUDED.message_name_cn,
                            signal_name_cn = EXCLUDED.signal_name_cn,
                            description_cn = EXCLUDED.description_cn,
                            unit_cn = EXCLUDED.unit_cn,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        can_id, can_id_hex, signal_name, full_signal_name,
                        message_name, message_name_cn,
                        signal.start, signal.length,
                        signal.byte_order, signal.is_signed,
                        signal.scale, signal.offset,
                        signal.minimum, signal.maximum,
                        signal_name_cn, description_cn, unit, unit_cn,
                        signal.comment, 'can_powertrain'  # 預設分類
                    ))

                    imported_count += 1
                    # 每次插入成功後立即 commit，避免單個失敗影響其他插入
                    self.db_manager.conn.commit()

                except Exception as e:
                    logger.error(f"插入 CAN 訊號失敗 {full_signal_name}: {e}")
                    # 回滾這個失敗的交易
                    self.db_manager.conn.rollback()
        logger.info(f"成功匯入 {imported_count} 個 CAN 訊號定義")
        return imported_count


def main():
    """主程式"""
    print("=== 訊號定義匯入工具 ===\n")

    # 連接資料庫
    try:
        db_manager = DatabaseManager()
        db_manager.connect()
        print("✓ 資料庫連接成功\n")
    except Exception as e:
        print(f"✗ 資料庫連接失敗: {e}")
        return

    # 建立資料表
    print("建立資料表...")
    try:
        with open('schema_signal_definitions.sql', 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        db_manager.cursor.execute(schema_sql)
        db_manager.conn.commit()
        print("✓ 資料表建立成功\n")
    except Exception as e:
        print(f"✗ 資料表建立失敗: {e}\n")

    # 建立匯入器
    importer = SignalDefinitionImporter(db_manager)

    # 匯入 Cereal 訊號
    print("--- 匯入 Cereal 訊號定義 ---")
    cereal_count = importer.import_cereal_signals('log.capnp')
    print(f"✓ 匯入了 {cereal_count} 個 Cereal 訊號\n")

    # 匯入 CAN 訊號
    print("--- 匯入 CAN 訊號定義 ---")
    can_count = importer.import_can_signals('vw_mqb.dbc')
    print(f"✓ 匯入了 {can_count} 個 CAN 訊號\n")

    # 統計
    print("=== 匯入完成 ===")
    print(f"Cereal 訊號: {cereal_count}")
    print(f"CAN 訊號: {can_count}")
    print(f"總計: {cereal_count + can_count}")

    # 關閉連接
    db_manager.disconnect()


if __name__ == '__main__':
    main()
