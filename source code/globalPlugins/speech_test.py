# -*- coding: UTF-8 -*-
"""
NVDA語音重排插件 - 修正處理邏輯版
正確處理NVDA的列表格式語音序列
"""

import globalPluginHandler
import speech
import speech.speech
import api
import ui
import logHandler
import re
import scriptHandler

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
        logHandler.log.error(f"語音重排處理錯誤: {str(e)}")
        return originalSpeak(speechSequence, *args, **kwargs)

def reorderSpeakObject(obj, *args, **kwargs):
    """攔截 speech.speakObject 函數"""
    global debugMode
    
    if debugMode:
        logHandler.log.info(f"攔截到 speakObject: {obj}, args: {args}")
    
    return originalSpeakObject(obj, *args, **kwargs)

def process_speech_reorder(speech_sequence):
    """處理語音序列重排的核心函數 - 修正版"""
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
    original_indices = []  # 記錄原始位置
    
    for i, item in enumerate(speech_sequence):
        if isinstance(item, str):
            text_items.append(item.strip())
            original_indices.append(i)
        else:
            other_items.append((i, item))  # 保存位置和項目
    
    # 過濾空字符串
    filtered_texts = [text for text in text_items if text]
    
    if len(filtered_texts) < 2:
        return speech_sequence
    
    # 識別控件類型和內容
    control_items = []
    content_items = []
    
    for text in filtered_texts:
        if text in control_types:
            control_items.append(text)
        else:
            content_items.append(text)
    
    # 如果沒有控件類型或沒有內容，不重排
    if not control_items or not content_items:
        return speech_sequence
    
    # 重排：內容在前，控件類型在後
    reordered_texts = content_items + control_items
    
    # 重構最終序列
    result = reordered_texts.copy()
    
    # 添加其他非文本項目到最後
    for pos, item in other_items:
        result.append(item)
    
    return result

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """語音重排全局插件 - 修正版"""
    
    scriptCategory = "語音重排"
    
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
        
        logHandler.log.info("語音重排插件已啟動 - 修正版")
    
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
        
        logHandler.log.info("語音重排插件已關閉")
    
    def script_toggleSpeechReorder(self, gesture):
        """切換語音重排功能"""
        global speechReorderEnabled
        
        speechReorderEnabled = not speechReorderEnabled
        
        if speechReorderEnabled:
            ui.message("語音重排已開啟：純文本將在控件信息之前朗讀")
        else:
            ui.message("語音重排已關閉：恢復原始朗讀順序")
        
        logHandler.log.info(f"語音重排功能已{'開啟' if speechReorderEnabled else '關閉'}")
    
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
        """測試重排功能"""
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
        """顯示狀態"""
        ui.message(f"語音重排: {'開啟' if speechReorderEnabled else '關閉'}")
        ui.message(f"調試模式: {'開啟' if debugMode else '關閉'}")
        
        if lastProcessedSequence:
            ui.message(f"最後處理: {lastProcessedSequence}")
    
    # 快捷鍵說明
    script_toggleSpeechReorder.__doc__ = "切換語音重排功能"
    script_toggleDebugMode.__doc__ = "切換調試模式"
    script_testReorder.__doc__ = "測試語音重排功能"
    script_showStatus.__doc__ = "顯示插件狀態"
    
    # 快捷鍵綁定
    __gestures = {
        "kb:NVDA+ctrl+shift+y": "toggleSpeechReorder",
        "kb:NVDA+ctrl+shift+i": "toggleDebugMode",
        "kb:NVDA+ctrl+shift+u": "testReorder", 
        "kb:NVDA+ctrl+shift+o": "showStatus"
    }