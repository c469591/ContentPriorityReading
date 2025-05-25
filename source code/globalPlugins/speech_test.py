# -*- coding: UTF-8 -*-
"""
內容優先朗讀插件（純API版本）
讓純文本內容在控件信息之前朗讀，提供更好的閱讀體驗
完全依賴NVDA本地化API，支援所有語言
快捷鍵：NVDA+Ctrl+Shift+Y 切換功能開關
"""

import globalPluginHandler
import speech
import speech.speech
import api
import ui
import logHandler
import controlTypes

# 全局變量
originalSpeak = None
originalSpeakObject = None
speechReorderEnabled = False
debugMode = False
lastProcessedSequence = []

# 獲取本地化控件類型名稱的緩存
_localized_control_types = None
_api_source_info = None

def get_localized_control_types():
    """純API版本：完全依賴NVDA的本地化系統獲取控件類型名稱"""
    global _localized_control_types, _api_source_info
    
    if _localized_control_types is not None:
        return _localized_control_types
    
    control_types = []
    api_info = {
        'total_roles': 0,
        'successful_roles': 0,
        'api_method': 'unknown',
        'failed_roles': []
    }
    
    # 動態獲取所有Role枚舉值
    all_roles = []
    try:
        for attr_name in dir(controlTypes.Role):
            if not attr_name.startswith('_') and not attr_name in ['name', 'value']:
                try:
                    role = getattr(controlTypes.Role, attr_name)
                    # 檢查是否是有效的枚舉值
                    if hasattr(role, 'name') and hasattr(role, 'value'):
                        all_roles.append(role)
                        api_info['total_roles'] += 1
                except Exception as e:
                    if debugMode:
                        logHandler.log.debug(f"跳過無效角色 {attr_name}: {str(e)}")
                    continue
    except Exception as e:
        logHandler.log.error(f"獲取Role枚舉時出錯: {str(e)}")
        return []
    
    if debugMode:
        logHandler.log.info(f"找到 {len(all_roles)} 個Role枚舉值")
    
    # 嘗試不同的API方法獲取本地化名稱
    for role in all_roles:
        localized_name = ""
        
        try:
            # 方法1：使用新版本的roleLabels
            if hasattr(controlTypes, 'roleLabels') and controlTypes.roleLabels:
                localized_name = controlTypes.roleLabels.get(role, "")
                if localized_name and api_info['api_method'] == 'unknown':
                    api_info['api_method'] = 'controlTypes.roleLabels'
            
            # 方法2：使用舊版本的speechRoleLabels（備用）
            if not localized_name and hasattr(controlTypes, 'speechRoleLabels'):
                localized_name = controlTypes.speechRoleLabels.get(role, "")
                if localized_name and api_info['api_method'] == 'unknown':
                    api_info['api_method'] = 'controlTypes.speechRoleLabels'
            
            # 方法3：嘗試通過其他可能的屬性
            if not localized_name:
                # 檢查是否有其他本地化相關的屬性
                for attr in ['displayString', 'localizedString', 'label']:
                    if hasattr(role, attr):
                        try:
                            localized_name = getattr(role, attr, "")
                            if localized_name and api_info['api_method'] == 'unknown':
                                api_info['api_method'] = f'role.{attr}'
                            break
                        except:
                            continue
            
            # 如果成功獲取到本地化名稱
            if localized_name and localized_name.strip():
                clean_name = localized_name.strip()
                if clean_name not in control_types:  # 避免重複
                    control_types.append(clean_name)
                    api_info['successful_roles'] += 1
                    
                    if debugMode:
                        logHandler.log.debug(f"成功獲取 {role.name} -> '{clean_name}'")
            else:
                api_info['failed_roles'].append(role.name)
                
        except Exception as e:
            api_info['failed_roles'].append(f"{role.name}({str(e)})")
            if debugMode:
                logHandler.log.debug(f"獲取角色 {role.name} 本地化名稱失敗: {str(e)}")
    
    # 緩存結果和API信息
    _localized_control_types = control_types
    _api_source_info = api_info
    
    # 記錄獲取結果
    success_rate = (api_info['successful_roles'] / api_info['total_roles'] * 100) if api_info['total_roles'] > 0 else 0
    logHandler.log.info(f"純API獲取控件類型完成: {api_info['successful_roles']}/{api_info['total_roles']} ({success_rate:.1f}%), 使用方法: {api_info['api_method']}")
    
    if debugMode:
        logHandler.log.info(f"獲取到的本地化控件類型: {control_types}")
        if api_info['failed_roles']:
            logHandler.log.debug(f"獲取失敗的角色: {api_info['failed_roles'][:10]}")  # 只顯示前10個
    
    return control_types

def reorderSpeak(speechSequence, *args, **kwargs):
    """重排語音序列的攔截函數"""
    global speechReorderEnabled, lastProcessedSequence, debugMode
    
    # 調試模式：總是記錄
    if debugMode:
        logHandler.log.info(f"攔截到語音序列: {speechSequence}")
    
    if not speechReorderEnabled:
        return originalSpeak(speechSequence, *args, **kwargs)
    
    try:
        # 處理語音序列重排
        reordered_sequence = process_speech_reorder(speechSequence)
        
        if debugMode and reordered_sequence != speechSequence:
            logHandler.log.info(f"原始序列: {speechSequence}")
            logHandler.log.info(f"重排序列: {reordered_sequence}")
        
        lastProcessedSequence = reordered_sequence.copy()
        return originalSpeak(reordered_sequence, *args, **kwargs)
    except Exception as e:
        if debugMode:
            logHandler.log.error(f"語音重排處理錯誤: {str(e)}")
        return originalSpeak(speechSequence, *args, **kwargs)

def reorderSpeakObject(obj, *args, **kwargs):
    """攔截 speech.speakObject 函數"""
    global debugMode
    
    if debugMode:
        logHandler.log.info(f"攔截到 speakObject: {obj}, args: {args}")
    
    return originalSpeakObject(obj, *args, **kwargs)

def process_speech_reorder(speech_sequence):
    """處理語音序列重排的核心函數"""
    if not speech_sequence or len(speech_sequence) < 2:
        return speech_sequence
    
    # 獲取本地化控件類型列表
    control_types = get_localized_control_types()
    
    if not control_types:
        if debugMode:
            logHandler.log.warning("無法獲取本地化控件類型，跳過重排")
        return speech_sequence
    
    # 分離文本項目和其他項目
    text_items = []
    control_items = []
    other_items = []
    content_items = []
    
    for item in speech_sequence:
        if isinstance(item, str) and item.strip():
            text = item.strip()
            
            # 檢查是否為控件類型（精確匹配或包含匹配）
            is_control = False
            for control_type in control_types:
                if text == control_type or control_type in text:
                    control_items.append(text)
                    is_control = True
                    if debugMode:
                        logHandler.log.debug(f"識別為控件類型: '{text}' (匹配: '{control_type}')")
                    break
            
            if not is_control:
                content_items.append(text)
                if debugMode:
                    logHandler.log.debug(f"識別為內容: '{text}'")
        else:
            other_items.append(item)
            if debugMode:
                logHandler.log.debug(f"識別為其他項目: {type(item)} {item}")
    
    # 如果沒有控件類型或沒有內容，不重排
    if not control_items or not content_items:
        if debugMode:
            logHandler.log.debug(f"不進行重排 - 控件項目: {len(control_items)}, 內容項目: {len(content_items)}")
        return speech_sequence
    
    # 重排：內容在前，控件類型在後，其他項目保持在相應位置
    result = content_items + control_items + other_items
    
    if debugMode:
        logHandler.log.info(f"重排完成: 內容({len(content_items)}) + 控件({len(control_items)}) + 其他({len(other_items)})")
    
    return result

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """內容優先朗讀插件（純API版本）"""
    
    scriptCategory = "內容優先朗讀"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global originalSpeak, originalSpeakObject, _localized_control_types
        
        # 清除緩存，重新獲取本地化控件類型
        _localized_control_types = None
        
        # 備份原始語音函數
        originalSpeak = speech.speak
        
        # 嘗試攔截多個語音函數
        try:
            if hasattr(speech, 'speakObject'):
                originalSpeakObject = speech.speakObject
                speech.speakObject = reorderSpeakObject
        except:
            pass
            
        try:
            if hasattr(speech.speech, 'speak'):
                speech.speech.speak = reorderSpeak
        except:
            pass
        
        # 主要攔截
        speech.speak = reorderSpeak
        
        # 預先載入控件類型（初始化時進行）
        try:
            control_types = get_localized_control_types()
            logHandler.log.info(f"內容優先朗讀插件已啟動 - 載入了 {len(control_types)} 個本地化控件類型")
        except Exception as e:
            logHandler.log.error(f"初始化控件類型時出錯: {str(e)}")
    
    def terminate(self):
        """插件終止時恢復原始函數"""
        global originalSpeak, originalSpeakObject, _localized_control_types, _api_source_info
        
        if originalSpeak:
            speech.speak = originalSpeak
            
        if originalSpeakObject:
            try:
                speech.speakObject = originalSpeakObject
            except:
                pass
                
        try:
            if hasattr(speech.speech, 'speak'):
                speech.speech.speak = originalSpeak
        except:
            pass
        
        # 清除緩存
        _localized_control_types = None
        _api_source_info = None
        
        logHandler.log.info("內容優先朗讀插件已關閉")
    
    # 重新載入本地化控件類型
    def refresh_localized_types(self):
        """重新載入本地化控件類型緩存"""
        global _localized_control_types, _api_source_info
        _localized_control_types = None
        _api_source_info = None
        
        try:
            control_types = get_localized_control_types()
            ui.message(f"已重新載入 {len(control_types)} 個本地化控件類型")
            logHandler.log.info("已重新載入本地化控件類型緩存")
        except Exception as e:
            ui.message(f"重新載入失敗：{str(e)}")
            logHandler.log.error(f"重新載入控件類型失敗: {str(e)}")
    
    def script_toggleSpeechReorder(self, gesture):
        """切換內容優先朗讀功能"""
        global speechReorderEnabled
        
        speechReorderEnabled = not speechReorderEnabled
        
        if speechReorderEnabled:
            ui.message("內容優先朗讀已開啟")
        else:
            ui.message("內容優先朗讀已關閉")
        
        logHandler.log.info(f"內容優先朗讀功能已{'開啟' if speechReorderEnabled else '關閉'}")
    
    def script_toggleDebugMode(self, gesture):
        """切換調試模式"""
        global debugMode
        
        debugMode = not debugMode
        
        if debugMode:
            ui.message("調試模式已開啟")
        else:
            ui.message("調試模式已關閉")
        
        logHandler.log.info(f"調試模式已{'開啟' if debugMode else '關閉'}")
    
    def script_diagnoseAPI(self, gesture):
        """診斷API狀態和控件類型來源"""
        global _api_source_info
        
        try:
            control_types = get_localized_control_types()
            
            ui.message("=== API診斷報告 ===")
            
            if _api_source_info:
                info = _api_source_info
                success_rate = (info['successful_roles'] / info['total_roles'] * 100) if info['total_roles'] > 0 else 0
                
                ui.message(f"API方法: {info['api_method']}")
                ui.message(f"成功率: {info['successful_roles']}/{info['total_roles']} ({success_rate:.1f}%)")
                ui.message(f"獲取到 {len(control_types)} 個控件類型")
                
                if len(control_types) > 0:
                    ui.message(f"範例: {', '.join(control_types[:5])}")
                
                if success_rate < 50:
                    ui.message("⚠️ API獲取成功率較低，可能需要檢查NVDA版本兼容性")
                elif success_rate >= 80:
                    ui.message("✅ API工作正常")
                else:
                    ui.message("⚡ API部分工作，建議檢查")
            else:
                ui.message("❌ 無API診斷信息，可能初始化失敗")
                
        except Exception as e:
            ui.message(f"診斷時發生錯誤：{str(e)}")
            logHandler.log.error(f"API診斷錯誤: {str(e)}")
    
    def script_testReorder(self, gesture):
        """測試語音重排功能"""
        control_types = get_localized_control_types()
        
        if not control_types:
            ui.message("無法測試：未獲取到控件類型")
            return
        
        # 使用實際獲取到的控件類型進行測試
        test_sequences = [
            [control_types[0] if len(control_types) > 0 else '未知', '', '測試內容1'],
            ['測試內容2', control_types[1] if len(control_types) > 1 else '未知', ''],
            [control_types[2] if len(control_types) > 2 else '未知', '測試內容3', '額外信息']
        ]
        
        ui.message("測試語音重排功能：")
        
        for i, seq in enumerate(test_sequences, 1):
            reordered = process_speech_reorder(seq)
            ui.message(f"測試 {i}")
            ui.message(f"原始: {seq}")
            ui.message(f"重排: {reordered}")
    
    def script_showControlTypes(self, gesture):
        """顯示當前本地化的控件類型"""
        try:
            control_types = get_localized_control_types()
            
            if control_types:
                ui.message(f"當前本地化控件類型共 {len(control_types)} 個：")
                
                # 分批顯示，避免信息過多
                batch_size = 8
                for i in range(0, len(control_types), batch_size):
                    batch = control_types[i:i + batch_size]
                    ui.message(f"第 {i//batch_size + 1} 批: {', '.join(batch)}")
                    
                    if i + batch_size >= 24:  # 最多顯示3批
                        remaining = len(control_types) - i - batch_size
                        if remaining > 0:
                            ui.message(f"還有 {remaining} 個...")
                        break
            else:
                ui.message("❌ 無法獲取本地化控件類型")
        except Exception as e:
            ui.message(f"獲取控件類型時發生錯誤：{str(e)}")
            logHandler.log.error(f"獲取控件類型錯誤: {str(e)}")
    
    def script_refreshLocalizedTypes(self, gesture):
        """重新載入本地化控件類型"""
        self.refresh_localized_types()
    
    def script_showStatus(self, gesture):
        """顯示插件狀態"""
        ui.message(f"內容優先朗讀: {'開啟' if speechReorderEnabled else '關閉'}")
        ui.message(f"調試模式: {'開啟' if debugMode else '關閉'}")
        
        try:
            control_types = get_localized_control_types()
            ui.message(f"已載入 {len(control_types)} 個本地化控件類型")
            
            if _api_source_info:
                ui.message(f"API方法: {_api_source_info['api_method']}")
        except Exception as e:
            ui.message(f"獲取狀態時出錯：{str(e)}")
        
        if lastProcessedSequence:
            ui.message(f"最後處理: {lastProcessedSequence}")
    
    # 快捷鍵說明
    script_toggleSpeechReorder.__doc__ = "切換內容優先朗讀功能開關"
    script_toggleDebugMode.__doc__ = "切換調試模式，用於查看語音序列處理詳情"
    script_diagnoseAPI.__doc__ = "診斷API狀態和控件類型獲取情況"
    script_testReorder.__doc__ = "測試語音重排功能，演示重排效果"
    script_showControlTypes.__doc__ = "顯示當前本地化的控件類型列表"
    script_refreshLocalizedTypes.__doc__ = "重新載入本地化控件類型緩存"
    script_showStatus.__doc__ = "顯示插件當前狀態和最後處理的序列"
    
    # 快捷鍵綁定 - 只綁定主要功能
    __gestures = {
        "kb:NVDA+ctrl+shift+y": "toggleSpeechReorder"
        # 其他功能沒有預設快捷鍵，用戶可透過NVDA輸入手勢對話框自定義
        # 可用的功能：
        # - toggleDebugMode: 切換調試模式
        # - diagnoseAPI: 診斷API狀態  
        # - testReorder: 測試語音重排功能  
        # - showControlTypes: 顯示本地化控件類型
        # - refreshLocalizedTypes: 重新載入本地化控件類型
        # - showStatus: 顯示插件狀態
    }