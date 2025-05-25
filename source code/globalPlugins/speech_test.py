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

# 全局變量
originalSpeak = None
originalSpeakObject = None
speechReorderEnabled = False
debugMode = False
lastProcessedSequence = []

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
    
    # 控件類型列表
    control_types = [
        '連結', '按鈕', '標題', '編輯區', '核取方塊', '清單', '表格', 
        '對話方塊', '下拉方塊', '滑桿', '樹狀檢視', '功能表', '工具列', 
        '狀態列', '頁籤', '群組', '面板', '地標', '視窗', '文字方塊',
        '子功能表', '功能表項目'
    ]
    
    # 分離文本項目和其他項目
    text_items = []
    other_items = []
    
    for item in speech_sequence:
        if isinstance(item, str) and item.strip():
            text_items.append(item.strip())
        else:
            other_items.append(item)
    
    if len(text_items) < 2:
        return speech_sequence
    
    # 識別控件類型和內容
    control_items = []
    content_items = []
    
    for text in text_items:
        if text in control_types:
            control_items.append(text)
        else:
            content_items.append(text)
    
    # 如果沒有控件類型或沒有內容，不重排
    if not control_items or not content_items:
        return speech_sequence
    
    # 重排：內容在前，控件類型在後
    result = content_items + control_items + other_items
    return result

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """內容優先朗讀插件"""
    
    scriptCategory = "內容優先朗讀"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global originalSpeak, originalSpeakObject
        
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
        global originalSpeak, originalSpeakObject
        
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
        test_sequences = [
            ['連結', '', 'Web Hosting'],
            ['按鈕', '', '確定'],
            ['VPS Hosting', '連結', '']
        ]
        
        ui.message("測試語音重排功能：")
        
        for seq in test_sequences:
            reordered = process_speech_reorder(seq)
            ui.message(f"原始: {seq}")
            ui.message(f"重排: {reordered}")
    
    def script_showStatus(self, gesture):
        """顯示插件狀態"""
        ui.message(f"內容優先朗讀: {'開啟' if speechReorderEnabled else '關閉'}")
        ui.message(f"調試模式: {'開啟' if debugMode else '關閉'}")
        
        if lastProcessedSequence:
            ui.message(f"最後處理: {lastProcessedSequence}")
    
    # 快捷鍵說明
    script_toggleSpeechReorder.__doc__ = "切換內容優先朗讀功能開關"
    script_toggleDebugMode.__doc__ = "切換調試模式，用於查看語音序列處理詳情"
    script_testReorder.__doc__ = "測試語音重排功能，演示重排效果"
    script_showStatus.__doc__ = "顯示插件當前狀態和最後處理的序列"
    
    # 快捷鍵綁定 - 只綁定主要功能
    __gestures = {
        "kb:NVDA+ctrl+shift+y": "toggleSpeechReorder"
        # 其他功能沒有預設快捷鍵，用戶可透過NVDA輸入手勢對話框自定義
        # 可用的功能：
        # - toggleDebugMode: 切換調試模式
        # - testReorder: 測試語音重排功能  
        # - showStatus: 顯示插件狀態
    }