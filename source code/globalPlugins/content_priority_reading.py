# -*- coding: UTF-8 -*-
# 內容優先朗讀插件
# 使用官方 filter_speechSequence API 和自定義 SpeechCommand 標記
# 精確識別控件類型和狀態，避免純文字誤判

import globalPluginHandler
import speech
import speech.speech
from speech.commands import SpeechCommand
from speech.extensions import filter_speechSequence
import config
import ui
import logHandler

# 全局變量
originalGetPropertiesSpeech = None
speechReorderEnabled = False
debugMode = False

# 配置規格
CONFIG_SPEC = {
    "enabled": "boolean(default=False)",
    "debugMode": "boolean(default=False)",
}

# 屬性參數（需要移到最後朗讀的）
PROPERTY_PARAMS = {
    'role',           # 控件類型：連結、按鈕等
    'states',         # 狀態：選中、按下等
    'negativeStates', # 否定狀態：未選中等
    'current',        # aria-current
    'keyboardShortcut',  # 快捷鍵
    'positionInfo_level',  # 層級
    'positionInfo_indexInGroup',  # 項目位置
    'positionInfo_similarItemsInGroup',  # 總項目數
    'hasDetails',     # 有詳情
    'detailsRoles',   # 詳情類型
}

# 內容參數（優先朗讀的）
CONTENT_PARAMS = {
    'name',           # 名稱/標籤
    'value',          # 值
    'description',    # 描述
    'placeholder',    # 佔位符
    'cellCoordsText', # 單元格坐標
    'rowNumber',      # 行號
    'columnNumber',   # 列號
    'rowHeaderText',  # 行標題
    'columnHeaderText',  # 列標題
    'rowCount',       # 行數
    'columnCount',    # 列數
    'errorMessage',   # 錯誤訊息
}

# 自定義命令類，用於標記屬性類型文字（控件類型、狀態等）
class PropertyTextCommand(SpeechCommand):
    # 標記這是屬性類型文字，不是普通內容
    def __init__(
        self,
        text  # 屬性的本地化文字，類型：str
    ):
        self.text = text

    def __repr__(self):
        return f"PropertyTextCommand({self.text!r})"

# 攔截 getPropertiesSpeech，標記屬性類型
def internal_hooked_getPropertiesSpeech(
    reason=None,
    **propertyValues
):
    global originalGetPropertiesSpeech, debugMode

    # 調用原始函數獲取語音序列
    result = originalGetPropertiesSpeech(reason=reason, **propertyValues)

    # 如果結果為空，直接返回（保持原有邏輯，不會添加原本不朗讀的內容）
    if not result:
        return result

    # 判斷這次調用是生成屬性還是內容
    # 排除 _role, _states, _tableID 等內部參數
    actual_params = {k for k in propertyValues.keys() if not k.startswith('_')}

    is_property_call = bool(actual_params & PROPERTY_PARAMS)
    is_content_call = bool(actual_params & CONTENT_PARAMS)

    # 只有純屬性調用（沒有內容參數）才標記
    if is_property_call and not is_content_call:
        newResult = []
        for item in result:
            if isinstance(item, str) and item.strip():
                newResult.append(PropertyTextCommand(item))
                if debugMode:
                    logHandler.log.info(f"標記屬性: '{item}' (參數: {actual_params})")
            else:
                newResult.append(item)
        return newResult

    return result

# 語音序列過濾器，重排序列
def internal_reorder_speech_filter(
    speechSequence  # 原始語音序列，類型：list
):
    global speechReorderEnabled, debugMode

    if not speechSequence:
        return speechSequence

    # 如果功能關閉，只需要把 PropertyTextCommand 轉回字符串
    if not speechReorderEnabled:
        return [
            item.text if isinstance(item, PropertyTextCommand) else item
            for item in speechSequence
        ]

    # 功能開啟，進行重排
    try:
        # 分離不同類型的項目
        content_items = []
        property_items = []
        command_items = []

        for item in speechSequence:
            if isinstance(item, PropertyTextCommand):
                # 這是精確標記的屬性（控件類型、狀態等）
                property_items.append(item.text)
                if debugMode:
                    logHandler.log.info(f"識別屬性(標記): '{item.text}'")
            elif isinstance(item, str):
                if item.strip():
                    # 普通文字內容
                    content_items.append(item)
                    if debugMode:
                        logHandler.log.info(f"識別內容: '{item}'")
                else:
                    # 空字符串，保留在命令列表
                    command_items.append(item)
            elif isinstance(item, SpeechCommand):
                # 其他語音命令（暫停、音調等）
                command_items.append(item)
            else:
                command_items.append(item)

        # 如果沒有屬性或沒有內容，不重排，但仍需轉換 PropertyTextCommand
        if not property_items or not content_items:
            return [
                item.text if isinstance(item, PropertyTextCommand) else item
                for item in speechSequence
            ]

        # 重排：內容在前，屬性在後，命令在最後
        result = content_items + property_items + command_items

        if debugMode:
            logHandler.log.info(f"重排完成: 內容({len(content_items)}) + 屬性({len(property_items)}) + 命令({len(command_items)})")

        return result

    except Exception as e:
        if debugMode:
            logHandler.log.error(f"重排錯誤: {str(e)}")
        # 出錯時也要確保 PropertyTextCommand 被轉換
        return [
            item.text if isinstance(item, PropertyTextCommand) else item
            for item in speechSequence
        ]

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    # 內容優先朗讀插件

    scriptCategory = "內容優先朗讀"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global originalGetPropertiesSpeech, speechReorderEnabled, debugMode

        # 註冊配置規格
        config.conf.spec["contentPriorityReading"] = CONFIG_SPEC

        # 從配置讀取狀態
        speechReorderEnabled = config.conf["contentPriorityReading"]["enabled"]
        debugMode = config.conf["contentPriorityReading"]["debugMode"]

        # 備份並攔截 getPropertiesSpeech
        originalGetPropertiesSpeech = speech.speech.getPropertiesSpeech
        speech.speech.getPropertiesSpeech = internal_hooked_getPropertiesSpeech

        # 同時更新 speech 模組的引用（某些插件可能直接使用）
        if hasattr(speech, 'getPropertiesSpeech'):
            speech.getPropertiesSpeech = internal_hooked_getPropertiesSpeech

        # 註冊官方的語音序列過濾器
        filter_speechSequence.register(internal_reorder_speech_filter)

        status = "開啟" if speechReorderEnabled else "關閉"
        logHandler.log.info(f"內容優先朗讀插件已啟動，狀態: {status}")

    def terminate(self):
        # 插件終止時恢復原始函數
        global originalGetPropertiesSpeech

        # 取消註冊過濾器
        try:
            filter_speechSequence.unregister(internal_reorder_speech_filter)
        except:
            pass

        # 恢復 getPropertiesSpeech
        if originalGetPropertiesSpeech:
            speech.speech.getPropertiesSpeech = originalGetPropertiesSpeech
            if hasattr(speech, 'getPropertiesSpeech'):
                speech.getPropertiesSpeech = originalGetPropertiesSpeech

        logHandler.log.info("內容優先朗讀插件已關閉")

    # 保存配置的輔助函數
    def internal_save_config(self):
        global speechReorderEnabled, debugMode
        config.conf["contentPriorityReading"]["enabled"] = speechReorderEnabled
        config.conf["contentPriorityReading"]["debugMode"] = debugMode
        # 立即保存到磁盤
        try:
            config.conf.save()
        except:
            pass

    def script_toggleSpeechReorder(self, gesture):
        # 切換內容優先朗讀功能
        global speechReorderEnabled

        speechReorderEnabled = not speechReorderEnabled
        self.internal_save_config()

        if speechReorderEnabled:
            ui.message("內容優先朗讀已開啟")
        else:
            ui.message("內容優先朗讀已關閉")

        logHandler.log.info(f"內容優先朗讀功能已{'開啟' if speechReorderEnabled else '關閉'}")

    def script_toggleDebugMode(self, gesture):
        # 切換調試模式
        global debugMode

        debugMode = not debugMode
        self.internal_save_config()

        if debugMode:
            ui.message("調試模式已開啟")
        else:
            ui.message("調試模式已關閉")

        logHandler.log.info(f"調試模式已{'開啟' if debugMode else '關閉'}")

    def script_showStatus(self, gesture):
        # 顯示插件狀態
        ui.message(f"內容優先朗讀: {'開啟' if speechReorderEnabled else '關閉'}")
        ui.message(f"調試模式: {'開啟' if debugMode else '關閉'}")

    # 快捷鍵綁定
    __gestures = {
        "kb:NVDA+control+shift+y": "toggleSpeechReorder"
    }
