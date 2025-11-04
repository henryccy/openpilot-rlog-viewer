# -*- coding: utf-8 -*-
"""
訊號定義匯入工具 (SQLite 版本)
Import Signal Definitions Tool (SQLite)

功能：
1. 解析 log.capnp 取得所有 Cereal 訊號定義
2. 解析 DBC 檔案取得所有 CAN 訊號定義
3. 加上中文註解
4. 匯入到 SQLite 資料庫
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import capnp
from pathlib import Path
import logging
import json

from src.core.sqlite_manager import SQLiteManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 載入 Cap'n Proto schema
capnp.remove_import_hook()
log_capnp = capnp.load('log.capnp')
car_capnp = capnp.load('car.capnp')

# 嘗試載入 custom 和 legacy capnp（如果存在）
try:
    custom_capnp = capnp.load('custom.capnp')
    logger.info("已載入 custom.capnp")
except:
    custom_capnp = None
    logger.info("custom.capnp 不存在或無法載入")

try:
    legacy_capnp = capnp.load('legacy.capnp')
    logger.info("已載入 legacy.capnp")
except:
    legacy_capnp = None
    logger.info("legacy.capnp 不存在或無法載入")


class SignalDefinitionImporter:
    """訊號定義匯入器"""

    def __init__(self, db_manager: SQLiteManager):
        self.db_manager = db_manager

        # Cereal 訊號中文對照
        self.cereal_translations = {
            'aEgo': '加速度',
            'accFaulted': 'ACC故障',
            'allowBrake': '允許煞車',
            'allowThrottle': '允許油門',
            'alternativeExperience': '替代體驗模式',
            'autoResumeSng': '自動恢復停走',
            'awarenessActive': '主動注意力',
            'awarenessPassive': '被動注意力',
            'awarenessStatus': '注意力狀態',
            'brake': '煞車踏板',
            'brakePressed': '煞車踩下',
            'canErrorCounter': 'CAN錯誤計數',
            'canTimeout': 'CAN逾時',
            'canValid': 'CAN有效',
            'carBatteryCapacityUwh': '車輛電池容量',
            'carFaultedNonCritical': '非關鍵故障',
            'carStateMonoTime': '車輛狀態時間',
            'centerToFront': '質心到前軸距離',
            'charging': '充電中',
            'clutchPressed': '離合器踩下',
            'cruiseState': '定速狀態',
            'cumLagMs': '累計延遲',
            'current': '電流',
            'currentTime': '當前時間',
            'dashcamOnly': '僅行車記錄',
            'desiredCurvature': '期望曲率',
            'deviceStable': '設備穩定',
            'distanceLongPressed': '距離長按',
            'distanceRemaining': '剩餘距離',
            'distanceVeryLongPressed': '距離超長按',
            'distractedType': '分心類型',
            'dspExecutionTime': 'DSP執行時間',
            'enableBsm': '啟用盲點偵測',
            'enableDsu': '啟用駕駛輔助',
            'enableGasInterceptor': '啟用油門攔截',
            'engageable': '可啟用',
            'engaged': '系統啟用',
            'engineRpm': '引擎轉速',
            'espDisabled': 'ESP停用',
            'excessiveResets': '過度重置',
            'experimentalLongitudinalAvailable': '實驗縱向可用',
            'faceDetected': '偵測到臉部',
            'fanSpeedPercentDesired': '期望風扇速度',
            'fanSpeedRpm': '風扇轉速',
            'filteredSoundPressureWeightedDb': '濾波音壓加權',
            'flags': '車輛旗標',
            'forceDecel': '強制減速',
            'frameDropPerc': '丟幀率',
            'frameId': '影格編號',
            'frameIdExtra': '額外影格編號',
            'freeSpacePercent': '可用空間',
            'fuelGauge': '油量錶',
            'fuzzyFingerprint': '模糊指紋',
            'gas': '油門踏板',
            'gasPressed': '油門踩下',
            'gearShifter': '檔位',
            'gpsOK': 'GPS正常',
            'gpsTimeOfWeek': 'GPS週內時間',
            'gpsWeek': 'GPS週數',
            'gpuUsagePercent': 'GPU使用率',
            'hiStdCount': '高變異計數',
            'immediateQueueCount': '即時佇列數',
            'immediateQueueSize': '即時佇列大小',
            'inputsOK': '輸入正常',
            'isActiveMode': '主動模式',
            'isDistracted': '正在分心',
            'isLowStd': '低變異',
            'isRHD': '右駕駛座',
            'lastAthenaPingTime': '最後連線時間',
            'lastSpeed': '最後速度',
            'lastTime': '最後時間',
            'latActive': '橫向控制啟用',
            'lateralPlanMonoTime': '橫向規劃時間',
            'leftBlindspot': '左盲點',
            'leftBlinker': '左轉向燈',
            'locationMonoTime': '位置時間',
            'logTs': '日誌時間戳',
            'longActive': '縱向控制啟用',
            'longitudinalActuatorDelay': '縱向致動延遲',
            'longitudinalPlanMonoTime': '縱向規劃時間',
            'maneuverDistance': '操作距離',
            'mass': '車輛質量',
            'maxLateralAccel': '最大橫向加速度',
            'maxTempC': '最高溫度',
            'mdMonoTime': '模型資料時間',
            'measTime': '測量時間',
            'memoryTempC': '記憶體溫度',
            'memoryUsagePercent': '記憶體使用率',
            'minEnableSpeed': '最小啟用速度',
            'minSteerSpeed': '最小轉向速度',
            'modelExecutionTime': '模型執行時間',
            'modelMonoTime': '模型時間',
            'monotonicRawNanosDEPRECATD': '單調原始時間（已棄用）',
            'networkMetered': '網路計量',
            'notCar': '非汽車',
            'offroadPowerUsageUwh': '路外耗電量',
            'oncoming': '迎面而來',
            'openpilotLongitudinalControl': 'OP縱向控制',
            'passive': '被動模式',
            'pcmCruise': 'PCM定速',
            'poorVisionProb': '視線不佳機率',
            'posePitchOffset': '頭部俯仰偏移',
            'posePitchValidCount': '俯仰有效計數',
            'poseYawOffset': '頭部偏航偏移',
            'poseYawValidCount': '偏航有效計數',
            'posenetOK': '姿態網路正常',
            'powerDrawW': '功耗',
            'radarTimeStep': '雷達時間步',
            'radarUnavailable': '雷達不可用',
            'rawQueueCount': '原始佇列數',
            'rawQueueSize': '原始佇列大小',
            'regenBraking': '再生煞車',
            'renderTime': '渲染時間',
            'rightBlindspot': '右盲點',
            'rightBlinker': '右轉向燈',
            'rotationalInertia': '轉動慣量',
            'screenBrightnessPercent': '螢幕亮度',
            'secOcKeyAvailable': '安全OC金鑰可用',
            'secOcRequired': '需要安全OC',
            'sensorsOK': '感測器正常',
            'shouldStop': '應該停止',
            'showFull': '顯示完整',
            'signal': '訊號',
            'slcMapboxSpeedLimit': '地圖速限',
            'somPowerDrawW': 'SOM功耗',
            'soundPressure': '音壓',
            'soundPressureWeighted': '加權音壓',
            'soundPressureWeightedDb': '加權音壓分貝',
            'speedLimit': '速度限制',
            'standstill': '車輛靜止',
            'startAccel': '起步加速度',
            'startMonoTime': '起始時間',
            'started': '已啟動',
            'startedMonoTime': '啟動時間',
            'startingState': '起步狀態',
            'stationary': '靜止',
            'steerActuatorDelay': '轉向致動延遲',
            'steerFaultPermanent': '轉向永久故障',
            'steerFaultTemporary': '轉向暫時故障',
            'steerLimitAlert': '轉向限制警報',
            'steerLimitTimer': '轉向限制計時',
            'steerRatioRear': '後輪轉向比',
            'steeringAngleDeg': '方向盤角度',
            'steeringPressed': '方向盤被握持',
            'steeringTorque': '方向盤扭矩',
            'steeringTorqueEps': 'EPS方向盤扭矩',
            'stepChange': '步進變化',
            'stockAeb': '原廠AEB',
            'stockFcw': '原廠FCW',
            'stopAccel': '停止加速度',
            'stoppingControl': '停車控制',
            'stoppingDecelRate': '停車減速率',
            'themeUpdated': '主題已更新',
            'timeRemaining': '剩餘時間',
            'timeRemainingTypical': '典型剩餘時間',
            'timeSinceReset': '重置後時間',
            'timeStamp': '時間戳記',
            'timeToFirstFix': '首次定位時間',
            'timestampEof': '影格結束時間',
            'tireStiffnessFactor': '輪胎剛性係數',
            'tireStiffnessFront': '前輪胎剛性',
            'tireStiffnessRear': '後輪胎剛性',
            'togglesUpdated': '設定已更新',
            'trackId': '追蹤編號',
            'ufAccelCmd': '未濾波加速指令',
            'unixTimestampMillis': 'Unix時間戳',
            'vCruiseCluster': '儀表板定速',
            'vEgo': '車速',
            'vEgoCluster': '儀表板車速',
            'vEgoRaw': '原始車速',
            'vEgoStarting': '起步速度',
            'vEgoStopping': '停止速度',
            'voltage': '電壓',
            'wallTimeNanos': '系統時間',
            'wheelOnRightProb': '右駕機率',
            'wheelSpeedFactor': '輪速係數',
            'wheelbase': '軸距',
        }

        # 單位映射
        self.unit_map = {
            'm/s': '公尺/秒',
            'm/s²': '公尺/秒²',
            'm/s^2': '公尺/秒²',
            'deg': '度',
            'deg/s': '度/秒',
            'rad/s': '弧度/秒',
            'Nm': '牛頓·公尺',
            'kph': '公里/小時',
            'km/h': '公里/小時',
            'm': '公尺',
            '1/m': '1/公尺',
        }

    def _process_struct_fields_from_instance(self, msg_type: str, prefix: str, obj, imported_signals: set) -> int:
        """
        從實際物件實例遞迴處理結構體的所有欄位（類似 segment_importer 的方法）

        Args:
            msg_type: 訊息類型（如 carState）
            prefix: 欄位前綴（如 carState.wheelSpeeds）
            obj: 實際的 capnp 物件實例
            imported_signals: 已匯入的訊號集合（避免重複）

        Returns:
            匯入的訊號數量
        """
        count = 0

        try:
            if not hasattr(obj, 'schema'):
                return 0

            schema = obj.schema
            fields = schema.non_union_fields
        except:
            return 0

        for field_name in fields:
            full_name = f"{prefix}.{field_name}" if prefix else f"{msg_type}.{field_name}"

            # 避免重複匯入
            if full_name in imported_signals:
                continue

            try:
                field_value = getattr(obj, field_name)
                field_proto = schema.fields[field_name].proto
                type_enum = field_proto.slot.type.which()

                # 將 Cap'n Proto 型別轉換為可讀字串
                type_map = {
                    'void': 'Void',
                    'bool': 'Bool',
                    'int8': 'Int8',
                    'int16': 'Int16',
                    'int32': 'Int32',
                    'int64': 'Int64',
                    'uint8': 'UInt8',
                    'uint16': 'UInt16',
                    'uint32': 'UInt32',
                    'uint64': 'UInt64',
                    'float32': 'Float32',
                    'float64': 'Float64',
                    'text': 'Text',
                    'data': 'Data',
                    'list': 'List',
                    'enum': 'Enum',
                    'struct': 'Struct',
                    'interface': 'Interface',
                    'anyPointer': 'AnyPointer',
                }
                data_type = type_map.get(type_enum, 'Unknown')

                # 如果是結構體，遞迴處理
                if hasattr(field_value, 'schema'):
                    nested_count = self._process_struct_fields_from_instance(msg_type, full_name, field_value, imported_signals)
                    count += nested_count
                    if nested_count > 0:
                        logger.debug(f"  遞迴處理 {full_name}: 匯入 {nested_count} 個欄位")

                # 只匯入基本數值類型
                if data_type in ['Bool', 'Int8', 'Int16', 'Int32', 'Int64',
                                 'UInt8', 'UInt16', 'UInt32', 'UInt64',
                                 'Float32', 'Float64']:

                    # 從欄位名稱取得中文翻譯
                    name_cn = self.cereal_translations.get(field_name, '')

                    # 根據訊號名稱推測單位
                    unit = ''
                    unit_cn = ''
                    field_lower = field_name.lower()
                    if 'vego' in field_lower or ('speed' in field_lower and 'wheel' not in full_name.lower()):
                        unit = 'm/s'
                        unit_cn = '公尺/秒'
                    elif 'aego' in field_lower or 'accel' in field_lower:
                        unit = 'm/s²'
                        unit_cn = '公尺/秒²'
                    elif 'angle' in field_lower and 'deg' in field_name:
                        unit = 'deg'
                        unit_cn = '度'
                    elif 'rate' in field_lower and 'deg' in field_name:
                        unit = 'deg/s'
                        unit_cn = '度/秒'
                    elif 'wheel' in full_name.lower() and 'speed' in field_lower:
                        unit = 'm/s'
                        unit_cn = '公尺/秒'
                    elif 'torque' in field_lower:
                        unit = 'Nm'
                        unit_cn = '牛頓·公尺'

                    # 計算正確的 signal_name（用於 UNIQUE 約束）
                    # 對於嵌套結構，signal_name 應該包含完整路徑
                    if prefix:
                        if prefix.startswith(msg_type + '.'):
                            # 移除 message_type 前綴，例如 "radarState.leadOne" -> "leadOne"
                            struct_path = prefix[len(msg_type) + 1:]
                            signal_name = f"{struct_path}.{field_name}"  # "leadOne.dRel"
                        else:
                            signal_name = field_name
                    else:
                        signal_name = field_name

                    # 插入資料庫
                    try:
                        self.db_manager.cursor.execute("""
                            INSERT OR REPLACE INTO cereal_signal_definitions
                            (message_type, signal_name, full_name, data_type, unit, unit_cn, name_cn)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (msg_type, signal_name, full_name, data_type, unit, unit_cn, name_cn))
                        self.db_manager.conn.commit()
                        imported_signals.add(full_name)
                        count += 1
                    except Exception as e:
                        logger.error(f"插入訊號失敗 {full_name}: {e}")
                        self.db_manager.conn.rollback()

            except Exception as e:
                logger.debug(f"處理欄位 {full_name} 時出錯: {e}")
                continue

        return count

    def _process_struct_fields(self, msg_type: str, prefix: str, schema, imported_signals: set) -> int:
        """
        遞迴處理結構體的所有欄位（包含嵌套結構）

        Args:
            msg_type: 訊息類型（如 carState）
            prefix: 欄位前綴（如 carState.wheelSpeeds）
            schema: Cap'n Proto schema
            imported_signals: 已匯入的訊號集合（避免重複）

        Returns:
            匯入的訊號數量
        """
        count = 0

        try:
            fields = schema.non_union_fields
        except:
            return 0

        for field_name in fields:
            # 不跳過 DEPRECATED 欄位（實際資料中仍會記錄）
            # if 'DEPRECATED' in field_name:
            #     continue

            full_name = f"{prefix}.{field_name}" if prefix else f"{msg_type}.{field_name}"

            # 避免重複匯入
            if full_name in imported_signals:
                continue

            try:
                field_proto = schema.fields[field_name].proto
                type_enum = field_proto.slot.type.which()

                # 將 Cap'n Proto 型別轉換為可讀字串
                type_map = {
                    'void': 'Void',
                    'bool': 'Bool',
                    'int8': 'Int8',
                    'int16': 'Int16',
                    'int32': 'Int32',
                    'int64': 'Int64',
                    'uint8': 'UInt8',
                    'uint16': 'UInt16',
                    'uint32': 'UInt32',
                    'uint64': 'UInt64',
                    'float32': 'Float32',
                    'float64': 'Float64',
                    'text': 'Text',
                    'data': 'Data',
                    'list': 'List',
                    'enum': 'Enum',
                    'struct': 'Struct',
                    'interface': 'Interface',
                    'anyPointer': 'AnyPointer',
                }
                data_type = type_map.get(type_enum, 'Unknown')

                # 如果是結構體，遞迴處理
                if type_enum == 'struct':
                    try:
                        # 獲取嵌套結構的 typeId
                        nested_schema_id = field_proto.slot.type.struct.typeId

                        # 方法 1: 嘗試從所有模組載入（包括嵌套類型）
                        nested_modules = [car_capnp, log_capnp]
                        if custom_capnp:
                            nested_modules.append(custom_capnp)
                        if legacy_capnp:
                            nested_modules.append(legacy_capnp)

                        nested_loaded = False
                        for module in nested_modules:
                            try:
                                nested_class = module._get_type_by_id(nested_schema_id)
                                nested_count = self._process_struct_fields(msg_type, full_name, nested_class.schema, imported_signals)
                                count += nested_count
                                if nested_count > 0:
                                    logger.info(f"  遞迴處理 {full_name}: 匯入 {nested_count} 個欄位")
                                nested_loaded = True
                                break
                            except Exception as module_error:
                                logger.debug(f"  從模組載入 {full_name} 失敗: {module_error}")
                                continue

                        # 方法 2: 如果通過 typeId 找不到，嘗試通過 capnp schema node 直接訪問
                        if not nested_loaded:
                            try:
                                # 嘗試從 schema registry 直接獲取
                                import _capnp
                                nested_node = _capnp.schema_from_id(nested_schema_id)
                                if nested_node:
                                    nested_count = self._process_struct_fields(msg_type, full_name, nested_node, imported_signals)
                                    count += nested_count
                                    if nested_count > 0:
                                        logger.info(f"  遞迴處理 {full_name}: 匯入 {nested_count} 個欄位 (via schema registry)")
                                    nested_loaded = True
                            except Exception as registry_error:
                                logger.debug(f"  從 schema registry 載入 {full_name} 失敗: {registry_error}")

                        if not nested_loaded:
                            logger.warning(f"⚠️  無法載入嵌套結構 {full_name} (typeId: {nested_schema_id})")
                    except Exception as e:
                        logger.warning(f"⚠️  處理嵌套結構 {full_name} 時發生錯誤: {e}")

                # 只匯入基本數值類型（跳過 List, Struct, Enum 等複雜類型）
                if data_type in ['Bool', 'Int8', 'Int16', 'Int32', 'Int64',
                                 'UInt8', 'UInt16', 'UInt32', 'UInt64',
                                 'Float32', 'Float64']:

                    # 從欄位名稱取得中文翻譯
                    name_cn = self.cereal_translations.get(field_name, '')

                    # 根據訊號名稱推測單位
                    unit = ''
                    unit_cn = ''
                    field_lower = field_name.lower()
                    if 'vego' in field_lower or ('speed' in field_lower and 'wheel' not in full_name.lower()):
                        unit = 'm/s'
                        unit_cn = '公尺/秒'
                    elif 'aego' in field_lower or 'accel' in field_lower:
                        unit = 'm/s²'
                        unit_cn = '公尺/秒²'
                    elif 'angle' in field_lower and 'deg' in field_name:
                        unit = 'deg'
                        unit_cn = '度'
                    elif 'rate' in field_lower and 'deg' in field_name:
                        unit = 'deg/s'
                        unit_cn = '度/秒'
                    elif 'wheel' in full_name.lower() and 'speed' in field_lower:
                        unit = 'm/s'
                        unit_cn = '公尺/秒'
                    elif 'torque' in field_lower:
                        unit = 'Nm'
                        unit_cn = '牛頓·公尺'
                    elif 'gas' in field_lower or 'brake' in field_lower:
                        unit = '0-1'
                        unit_cn = '0-1'
                    elif 'fuel' in field_lower:
                        unit = '0-1'
                        unit_cn = '0-1'

                    # 計算正確的 signal_name（用於 UNIQUE 約束）
                    # 對於嵌套結構，signal_name 應該包含完整路徑
                    if prefix:
                        if prefix.startswith(msg_type + '.'):
                            # 移除 message_type 前綴，例如 "radarState.leadOne" -> "leadOne"
                            struct_path = prefix[len(msg_type) + 1:]
                            signal_name = f"{struct_path}.{field_name}"  # "leadOne.dRel"
                        else:
                            signal_name = field_name
                    else:
                        signal_name = field_name

                    # 插入到資料庫
                    try:
                        self.db_manager.cursor.execute("""
                            INSERT OR REPLACE INTO cereal_signal_definitions
                            (message_type, signal_name, full_name, data_type, unit, unit_cn, name_cn)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (msg_type, signal_name, full_name, data_type, unit, unit_cn, name_cn))

                        self.db_manager.conn.commit()
                        imported_signals.add(full_name)
                        count += 1

                    except Exception as e:
                        logger.error(f"插入訊號失敗 {full_name}: {e}")
                        self.db_manager.conn.rollback()

            except Exception as e:
                logger.debug(f"處理欄位 {full_name} 時出錯: {e}")
                continue

        return count

    def import_cereal_signals(self) -> int:
        """
        匯入 Cereal 訊號定義 - 動態解析所有訊號類型和欄位（包含嵌套結構）

        Returns:
            匯入的訊號數量
        """
        logger.info("開始匯入 Cereal 訊號定義")

        # 刪除所有舊的 Cereal 訊號定義
        logger.info("刪除舊的 Cereal 訊號定義...")
        try:
            self.db_manager.cursor.execute("DELETE FROM cereal_signal_definitions")
            self.db_manager.conn.commit()
            logger.info("已清空舊的訊號定義")
        except Exception as e:
            logger.error(f"刪除舊定義失敗: {e}")
            self.db_manager.conn.rollback()

        imported_count = 0
        imported_signals = set()  # 追蹤已匯入的訊號，避免重複

        # 取得 Event union 中的所有訊號類型
        event_schema = log_capnp.Event.schema
        union_fields = event_schema.union_fields

        logger.info(f"找到 {len(union_fields)} 個 Event union 欄位")

        # 遍歷所有訊號類型
        for msg_type in union_fields:
            # 跳過不需要的類型（不跳過 DEPRECATED，因為實際資料中仍會記錄）
            if msg_type in ['initData', 'can', 'sendcan', 'logMessage', 'errorLogMessage', 'androidLog']:
                continue

            try:
                # 取得訊號類型的 schema
                msg_schema = None
                msg_class = None
                msg_class_name = msg_type[0].upper() + msg_type[1:]

                # 依序從各個 capnp 模組嘗試載入
                capnp_modules = [
                    ('log.capnp', log_capnp),
                    ('car.capnp', car_capnp),
                ]
                if custom_capnp:
                    capnp_modules.append(('custom.capnp', custom_capnp))
                if legacy_capnp:
                    capnp_modules.append(('legacy.capnp', legacy_capnp))

                # 特殊處理：frogpilot 訊號需要轉換名稱
                # frogpilotCarState -> FrogPilotCarState
                if msg_type.startswith('frogpilot'):
                    frogpilot_class_name = 'FrogPilot' + msg_type[9].upper() + msg_type[10:]
                    if custom_capnp:
                        try:
                            msg_class = getattr(custom_capnp, frogpilot_class_name)
                            msg_schema = msg_class.schema
                            logger.debug(f"從 custom.capnp 找到 {msg_type} -> {frogpilot_class_name}")
                        except:
                            pass

                # 如果還沒找到，嘗試從各個模組
                if msg_schema is None:
                    for module_name, module in capnp_modules:
                        try:
                            msg_class = getattr(module, msg_class_name)
                            msg_schema = msg_class.schema
                            logger.debug(f"從 {module_name} 找到 {msg_type}")
                            break
                        except:
                            pass

                if msg_schema is None or msg_class is None:
                    logger.debug(f"無法取得 {msg_type} 的 schema 或 class")
                    continue

                # 創建一個空的實例，這樣就能訪問嵌套結構（類似 segment_importer 的方法）
                try:
                    msg_instance = msg_class.new_message()
                    # 使用基於實例的方法遞迴處理所有欄位
                    count = self._process_struct_fields_from_instance(msg_type, '', msg_instance, imported_signals)
                    imported_count += count

                    if count > 0:
                        logger.info(f"  {msg_type}: 匯入 {count} 個訊號")
                except Exception as instance_error:
                    logger.warning(f"  無法創建 {msg_type} 實例: {instance_error}，使用舊方法")
                    # 如果創建實例失敗，退回使用舊方法
                    count = self._process_struct_fields(msg_type, '', msg_schema, imported_signals)
                    imported_count += count

                    if count > 0:
                        logger.info(f"  {msg_type}: 匯入 {count} 個訊號 (fallback)")

            except Exception as e:
                logger.warning(f"處理訊號類型 {msg_type} 時出錯: {e}")
                continue

        logger.info(f"成功匯入 {imported_count} 個 Cereal 訊號定義")
        return imported_count

    def import_can_signals(self, dbc_path: str, dbc_name: str = None) -> int:
        """
        匯入 CAN 訊號定義

        Args:
            dbc_path: DBC 檔案路徑
            dbc_name: DBC 檔案名稱（用於資料庫記錄，如果為 None 則從路徑提取）

        Returns:
            匯入的訊號數量
        """
        from pathlib import Path
        import shutil

        if dbc_name is None:
            dbc_name = Path(dbc_path).name

        logger.info(f"開始匯入 CAN 訊號定義從 {dbc_path}")

        # 複製 DBC 檔案到 data/dbc/ 目錄
        try:
            dbc_dir = Path('data/dbc')
            dbc_dir.mkdir(parents=True, exist_ok=True)

            dest_path = dbc_dir / dbc_name
            if not dest_path.exists() or Path(dbc_path).resolve() != dest_path.resolve():
                shutil.copy2(dbc_path, dest_path)
                logger.info(f"已複製 DBC 檔案到: {dest_path}")
            else:
                logger.info(f"DBC 檔案已存在: {dest_path}")
        except Exception as e:
            logger.warning(f"複製 DBC 檔案失敗: {e}，將繼續使用原始路徑")

        try:
            # 動態導入 DBCParser
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.core.dbc_parser import DBCParser

            dbc_parser = DBCParser(dbc_path)
        except Exception as e:
            logger.error(f"無法載入 DBC: {e}")
            return 0

        # 刪除該 DBC 檔案的舊訊號定義
        logger.info(f"刪除 {dbc_name} 的舊訊號定義...")
        try:
            self.db_manager.cursor.execute(
                "DELETE FROM can_signal_definitions WHERE dbc_file = ?",
                (dbc_name,)
            )
            self.db_manager.conn.commit()
        except Exception as e:
            logger.error(f"刪除舊定義失敗: {e}")
            self.db_manager.conn.rollback()

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
                full_name = f"CAN_{can_id_hex}_{signal_name}"

                # 中文翻譯
                signal_name_cn = dbc_parser.translate_to_chinese(signal_name)
                description_cn = dbc_parser.translate_to_chinese(signal.comment) if signal.comment else signal_name_cn

                # 單位
                unit = signal.unit if signal.unit else ''
                unit_cn = dbc_parser.translate_to_chinese(unit) if unit else ''

                # 訊號屬性
                try:
                    self.db_manager.cursor.execute("""
                        INSERT OR REPLACE INTO can_signal_definitions
                        (dbc_file, can_id, can_id_hex, message_name, message_name_cn,
                         signal_name, full_name,
                         start_bit, length, byte_order, is_signed,
                         factor, offset, min_value, max_value,
                         signal_name_cn, description_cn, unit, unit_cn, comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        dbc_name, can_id, can_id_hex, message_name, message_name_cn,
                        signal_name, full_name,
                        signal.start, signal.length,
                        signal.byte_order, int(signal.is_signed),
                        signal.scale, signal.offset,
                        signal.minimum, signal.maximum,
                        signal_name_cn, description_cn, unit, unit_cn,
                        signal.comment
                    ))

                    imported_count += 1
                    # 每次插入成功後立即 commit
                    self.db_manager.conn.commit()

                except Exception as e:
                    logger.error(f"插入 CAN 訊號失敗 {full_name}: {e}")
                    self.db_manager.conn.rollback()

        logger.info(f"成功匯入 {imported_count} 個 CAN 訊號定義")
        return imported_count


def main():
    """主程式"""
    import argparse

    parser = argparse.ArgumentParser(description="Import signal definitions to SQLite")
    parser.add_argument('--db', help='SQLite database path', default=None)
    args = parser.parse_args()

    print("=" * 80)
    print("訊號定義匯入工具 (SQLite)")
    print("=" * 80)
    print()

    # 連接資料庫
    try:
        db_manager = SQLiteManager(args.db)
        if not db_manager.connect():
            print("✗ 資料庫連接失敗")
            return
        print(f"✓ 資料庫連接成功: {db_manager.db_path}")
        print()
    except Exception as e:
        print(f"✗ 資料庫連接失敗: {e}")
        return

    # 確保資料表存在
    print("確保資料表存在...")
    try:
        db_manager.create_tables()
        print("✓ 資料表已就緒")
        print()
    except Exception as e:
        print(f"✗ 資料表建立失敗: {e}")
        print()

    # 建立匯入器
    importer = SignalDefinitionImporter(db_manager)

    # 匯入 Cereal 訊號
    print("--- 匯入 Cereal 訊號定義 ---")
    cereal_count = importer.import_cereal_signals()
    print(f"✓ 匯入了 {cereal_count} 個 Cereal 訊號")
    print()

    # 統計
    print("=" * 80)
    print("匯入完成")
    print("=" * 80)
    print(f"Cereal 訊號: {cereal_count}")
    print(f"總計: {cereal_count}")
    print()

    # 關閉連接
    db_manager.disconnect()


if __name__ == '__main__':
    main()
