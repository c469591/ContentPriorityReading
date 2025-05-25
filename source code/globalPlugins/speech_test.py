# -*- coding: UTF-8 -*-
"""
內容優先朗讀插件
讓純文本內容在控件信息之前朗讀，提供更好的閱讀體驗
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

def get_localized_control_types():
    """獲取當前語言的本地化控件類型名稱"""
    global _localized_control_types
    
    if _localized_control_types is not None:
        return _localized_control_types
    
    control_types = []
    
    # 常用的控件角色 - 移除不存在的 SUBMENU
    common_roles = [
        controlTypes.Role.LINK,
        controlTypes.Role.BUTTON, 
        controlTypes.Role.HEADING,
        controlTypes.Role.EDITABLETEXT,
        controlTypes.Role.CHECKBOX,
        controlTypes.Role.LIST,
        controlTypes.Role.TABLE,
        controlTypes.Role.DIALOG,
        controlTypes.Role.COMBOBOX,
        controlTypes.Role.SLIDER,
        controlTypes.Role.TREEVIEW,
        controlTypes.Role.MENUBAR,
        controlTypes.Role.TOOLBAR,
        controlTypes.Role.STATUSBAR,
        controlTypes.Role.TAB,
        controlTypes.Role.GROUPING,
        controlTypes.Role.PANEL,
        controlTypes.Role.LANDMARK,
        controlTypes.Role.WINDOW,
        controlTypes.Role.MENUITEM
    ]
    
    # 嘗試添加可能存在的其他角色
    additional_roles = ['SUBMENU', 'TEXTFRAME', 'PANE', 'SEPARATOR']
    for role_name in additional_roles:
        try:
            role = getattr(controlTypes.Role, role_name, None)
            if role is not None:
                common_roles.append(role)
        except:
            continue
    
    for role in common_roles:
        try:
            # 獲取本地化名稱
            if hasattr(controlTypes, 'roleLabels'):
                localized_name = controlTypes.roleLabels.get(role, "")
            else:
                # 備用方案：舊版本NVDA可能使用不同的屬性名
                localized_name = getattr(controlTypes, 'speechRoleLabels', {}).get(role, "")
            
            if localized_name and localized_name.strip():
                control_types.append(localized_name.strip())
        except Exception as e:
            if debugMode:
                logHandler.log.debug(f"獲取角色 {role} 的本地化名稱時出錯: {str(e)}")
            continue
    
    # 手動添加常見的本地化控件類型（從日誌中觀察到的）
    manual_types = [
        '連結', '按鈕', '標題', '編輯區', '核取方塊', '清單', '表格', 
        '對話方塊', '下拉方塊', '滑桿', '樹狀檢視', '功能表', '工具列', 
        '狀態列', '頁籤', '群組', '面板', '地標', '視窗', '文字方塊',
        '子功能表', '功能表項目'  # 添加從日誌中看到的"子功能表"
    ]
    
    # 合併並去重
    all_types = list(set(control_types + manual_types))
    
    # 緩存結果
    _localized_control_types = all_types
    
    if debugMode:
        logHandler.log.info(f"獲取到的本地化控件類型: {all_types}")
    
    return all_types

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
        # 如果無法獲取本地化控件類型，返回原序列
        return speech_sequence
    
    # 分離文本項目和其他項目
    text_items = []
    control_items = []
    other_items = []
    content_items = []
    
    for item in speech_sequence:
        if isinstance(item, str) and item.strip():
            text = item.strip()
            if text in control_types:
                control_items.append(text)
            else:
                # 進一步檢查是否包含控件類型關鍵詞
                is_control = False
                for control_type in control_types:
                    if control_type in text:
                        control_items.append(text)
                        is_control = True
                        break
                if not is_control:
                    content_items.append(text)
        else:
            other_items.append(item)
    
    # 如果沒有控件類型或沒有內容，不重排
    if not control_items or not content_items:
        return speech_sequence
    
    # 重排：內容在前，控件類型在後，其他項目保持在相應位置
    result = content_items + control_items + other_items
    return result

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """內容優先朗讀插件"""
    
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
        
        logHandler.log.info("內容優先朗讀插件已啟動")
    
    def terminate(self):
        """插件終止時恢復原始函數"""
        global originalSpeak, originalSpeakObject, _localized_control_types
        
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
        
        logHandler.log.info("內容優先朗讀插件已關閉")
    
    # 刷新本地化控件類型的方法（當語言設置改變時使用）
    def refresh_localized_types(self):
        """刷新本地化控件類型緩存"""
        global _localized_control_types
        _localized_control_types = None
        get_localized_control_types()
        ui.message("已刷新本地化控件類型")
        logHandler.log.info("已刷新本地化控件類型緩存")
    
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
        # 使用日誌中實際看到的語音序列進行測試
        test_sequences = [
            ['連結', '', 'arrow_drop_down'],
            ['偏好(P)', '子功能表', 'p'],
            ['檢視事件記錄(L)', '功能表項目', 'l']
        ]
        
        ui.message("測試語音重排功能：")
        
        for seq in test_sequences:
            reordered = process_speech_reorder(seq)
            ui.message(f"原始: {seq}")
            ui.message(f"重排: {reordered}")
    
    def script_showControlTypes(self, gesture):
        """顯示當前本地化的控件類型"""
        try:
            control_types = get_localized_control_types()
            
            if control_types:
                ui.message(f"當前本地化控件類型共 {len(control_types)} 個：")
                ui.message(", ".join(control_types[:10]))  # 只顯示前10個
                if len(control_types) > 10:
                    ui.message(f"還有 {len(control_types) - 10} 個...")
            else:
                ui.message("無法獲取本地化控件類型")
        except Exception as e:
            ui.message(f"獲取控件類型時發生錯誤：{str(e)}")
            logHandler.log.error(f"獲取控件類型錯誤: {str(e)}")
    
    def script_refreshLocalizedTypes(self, gesture):
        """刷新本地化控件類型"""
        self.refresh_localized_types()
    
    def script_showStatus(self, gesture):
        """顯示插件狀態"""
        ui.message(f"內容優先朗讀: {'開啟' if speechReorderEnabled else '關閉'}")
        ui.message(f"調試模式: {'開啟' if debugMode else '關閉'}")
        
        try:
            control_types = get_localized_control_types()
            ui.message(f"已載入 {len(control_types)} 個本地化控件類型")
        except Exception as e:
            ui.message(f"獲取控件類型狀態時出錯：{str(e)}")
        
        if lastProcessedSequence:
            ui.message(f"最後處理: {lastProcessedSequence}")
    
    # 快捷鍵說明
    script_toggleSpeechReorder.__doc__ = "切換內容優先朗讀功能開關"
    script_toggleDebugMode.__doc__ = "切換調試模式，用於查看語音序列處理詳情"
    script_testReorder.__doc__ = "測試語音重排功能，演示重排效果"
    script_showControlTypes.__doc__ = "顯示當前本地化的控件類型列表"
    script_refreshLocalizedTypes.__doc__ = "刷新本地化控件類型緩存"
    script_showStatus.__doc__ = "顯示插件當前狀態和最後處理的序列"
    
    # 快捷鍵綁定 - 只綁定主要功能
    __gestures = {
        "kb:NVDA+ctrl+shift+y": "toggleSpeechReorder"
        # 其他功能沒有預設快捷鍵，用戶可透過NVDA輸入手勢對話框自定義
        # 可用的功能：
        # - toggleDebugMode: 切換調試模式
        # - testReorder: 測試語音重排功能  
        # - showControlTypes: 顯示本地化控件類型
        # - refreshLocalizedTypes: 刷新本地化控件類型
        # - showStatus: 顯示插件狀態
    }