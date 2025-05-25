# -*- coding: UTF-8 -*-
"""
內容優先朗讀插件（兼容谷歌翻翻看版本）
同時攔截 speech.speak 和 speech.speech.speak，確保與翻譯插件完全兼容
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
originalSpeechSpeak = None
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
    content_items = []
    control_items = []
    other_items = []
    
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

# 攔截 speech.speak 的函數
def reorderSpeak(speechSequence, *args, **kwargs):
    """攔截 speech.speak 並重排序"""
    global speechReorderEnabled, lastProcessedSequence, debugMode, originalSpeak
    
    if debugMode:
        logHandler.log.info(f"speech.speak 攔截: {speechSequence}")
    
    if not speechReorderEnabled:
        return originalSpeak(speechSequence, *args, **kwargs)
    
    try:
        # 處理語音序列重排
        reordered_sequence = process_speech_reorder(speechSequence)
        
        if debugMode and reordered_sequence != speechSequence:
            logHandler.log.info(f"speech.speak 重排 - 原始: {speechSequence}")
            logHandler.log.info(f"speech.speak 重排 - 結果: {reordered_sequence}")
        
        lastProcessedSequence = list(reordered_sequence) if isinstance(reordered_sequence, (list, tuple)) else [reordered_sequence]
        return originalSpeak(reordered_sequence, *args, **kwargs)
        
    except Exception as e:
        if debugMode:
            logHandler.log.error(f"speech.speak 重排錯誤: {str(e)}")
        return originalSpeak(speechSequence, *args, **kwargs)

# 攔截 speech.speech.speak 的函數
def reorderSpeechSpeak(speechSequence, *args, **kwargs):
    """攔截 speech.speech.speak 並重排序（主要為了兼容谷歌翻翻看）"""
    global speechReorderEnabled, lastProcessedSequence, debugMode, originalSpeechSpeak
    
    if debugMode:
        logHandler.log.info(f"speech.speech.speak 攔截: {speechSequence}")
    
    if not speechReorderEnabled:
        return originalSpeechSpeak(speechSequence, *args, **kwargs)
    
    try:
        # 處理語音序列重排
        reordered_sequence = process_speech_reorder(speechSequence)
        
        if debugMode and reordered_sequence != speechSequence:
            logHandler.log.info(f"speech.speech.speak 重排 - 原始: {speechSequence}")
            logHandler.log.info(f"speech.speech.speak 重排 - 結果: {reordered_sequence}")
        
        lastProcessedSequence = list(reordered_sequence) if isinstance(reordered_sequence, (list, tuple)) else [reordered_sequence]
        return originalSpeechSpeak(reordered_sequence, *args, **kwargs)
        
    except Exception as e:
        if debugMode:
            logHandler.log.error(f"speech.speech.speak 重排錯誤: {str(e)}")
        return originalSpeechSpeak(speechSequence, *args, **kwargs)

def reorderSpeakObject(obj, *args, **kwargs):
    """攔截 speech.speakObject 函數"""
    global debugMode
    
    if debugMode:
        logHandler.log.info(f"攔截到 speakObject: {obj}, args: {args}")
    
    return originalSpeakObject(obj, *args, **kwargs)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """內容優先朗讀插件（兼容谷歌翻翻看版本）"""
    
    scriptCategory = "內容優先朗讀"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global originalSpeak, originalSpeechSpeak, originalSpeakObject, _localized_control_types
        
        # 清除緩存，重新獲取本地化控件類型
        _localized_control_types = None
        
        # **關鍵改進：同時備份兩個語音函數**
        # 備份 speech.speak
        originalSpeak = speech.speak
        
        # **備份 speech.speech.speak（谷歌翻翻看攔截的函數）**
        originalSpeechSpeak = speech.speech.speak
        
        # 嘗試攔截 speakObject
        try:
            if hasattr(speech, 'speakObject'):
                originalSpeakObject = speech.speakObject
                speech.speakObject = reorderSpeakObject
        except Exception as e:
            if debugMode:
                logHandler.log.debug(f"備份speakObject失敗: {str(e)}")
        
        # **同時攔截兩個語音函數**
        speech.speak = reorderSpeak
        speech.speech.speak = reorderSpeechSpeak
        
        # 預先載入控件類型
        try:
            control_types = get_localized_control_types()
            logHandler.log.info(f"內容優先朗讀插件已啟動 (兼容谷歌翻翻看模式) - 載入了 {len(control_types)} 個本地化控件類型")
        except Exception as e:
            logHandler.log.error(f"初始化控件類型時出錯: {str(e)}")
    
    def terminate(self):
        """插件終止時恢復原始函數"""
        global originalSpeak, originalSpeechSpeak, originalSpeakObject, _localized_control_types, _api_source_info
        
        # 恢復 speech.speak
        if originalSpeak:
            speech.speak = originalSpeak
        
        # **恢復 speech.speech.speak**
        if originalSpeechSpeak:
            speech.speech.speak = originalSpeechSpeak
            
        # 恢復 speakObject
        if originalSpeakObject:
            try:
                speech.speakObject = originalSpeakObject
            except:
                pass
        
        # 清除緩存
        _localized_control_types = None
        _api_source_info = None
        
        logHandler.log.info("內容優先朗讀插件已關閉")
    
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
        
        ui.message("測試語音重排功能（兼容翻譯插件模式）：")
        
        for i, seq in enumerate(test_sequences, 1):
            reordered = process_speech_reorder(seq)
            ui.message(f"測試 {i}")
            ui.message(f"原始: {seq}")
            ui.message(f"重排: {reordered}")
    
    def script_showStatus(self, gesture):
        """顯示插件狀態"""
        ui.message(f"內容優先朗讀: {'開啟' if speechReorderEnabled else '關閉'}")
        ui.message(f"調試模式: {'開啟' if debugMode else '關閉'}")
        ui.message("工作模式: 兼容谷歌翻翻看模式")
        
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
    script_toggleDebugMode.__doc__ = "切換調試模式"
    script_testReorder.__doc__ = "測試語音重排功能"
    script_showStatus.__doc__ = "顯示插件狀態"
    
    # 快捷鍵綁定
    __gestures = {
        "kb:NVDA+ctrl+shift+y": "toggleSpeechReorder"
    }