import os
import base64
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from openai import OpenAI
from dotenv import load_dotenv
load_dotenv(override=True)
from utils.logger_tool import logger


def _image_url(image: str) -> str:
    """本地图片转 data URL；HTTP(S) 图片地址保持原样。"""
    parsed = urlsplit(image)
    if parsed.scheme.lower() in {"http", "https"}:
        if not parsed.netloc:
            raise ValueError(f"图片 URL 无效：{image}")
        return image

    image_path = Path(image).expanduser()
    if not image_path.is_file():
        raise FileNotFoundError(f"本地图片不存在：{image_path}")

    mime_type, _ = mimetypes.guess_type(image_path.name)
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def parse_image(
    image: str,
    thinking: str = "none",
    *,
    prompt: str = "请用生动精炼的几句话准确的描述图片所呈现的内容",
) -> str:
    """"
    "none"	                    关闭思考
    "low" / "minimal"	        低强度思考（minimal 会被映射为 low）
    "medium"	                中等强度思考
    "xhigh" / "high" / "max"	高强度思考（默认值就是 xhigh）
    """
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    image_url = _image_url(image)

    # 3. 调用模型（注意：stream 必须为 True）
    stream = client.chat.completions.create(
        model="qwen3.8-omni-flash",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        stream=True,  # 必须开启流式传输
        stream_options={"include_usage": True},
        modalities=["text"],  # 仅输出文本
        reasoning_effort=thinking,
    )

    # 4. 收集流式返回的文本
    content = ""
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content += chunk.choices[0].delta.content
        # 打印 token 用量
        if hasattr(chunk, 'usage') and chunk.usage:
            logger.info(f"[Usage: {chunk.usage}]")
    return content

if __name__ == '__main__':
    chunk = parse_image("https://pic1.zhimg.com/v2-b766b1e85baa9acb4eb541dfeec273e9_r.jpg?source=1940ef5c")
    # for ck in chunk:
    #     print(ck, end="", flush=True)
    print(chunk)
