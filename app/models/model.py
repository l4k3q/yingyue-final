import json
import sqlite3
import urllib.parse
import requests
import tiktoken

from app.models.db import get_connection


def mask_api_key(api_key: str) -> str:
    if not api_key or len(api_key) <= 7:
        return '******'
    return api_key[:3] + '******' + api_key[-4:]


class AIModelRepository:
    @staticmethod
    def get_models(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM ai_models WHERE name LIKE ? OR model_id LIKE ? OR description LIKE ?",
                    (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
                )
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT * FROM ai_models WHERE name LIKE ? OR model_id LIKE ? OR description LIKE ? ORDER BY is_default DESC, created_at DESC LIMIT ? OFFSET ?",
                    (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", page_size, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM ai_models")
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT * FROM ai_models ORDER BY is_default DESC, created_at DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_model_by_id(model_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM ai_models WHERE id=?",
                (model_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_default_model():
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM ai_models WHERE is_default=1 AND status=1 ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_model(name: str, model_id: str, api_key: str, base_url: str,
                     temperature: float = 0.7, max_tokens: int = 4096,
                     top_p: float = 0.9, frequency_penalty: float = 0.0,
                     presence_penalty: float = 0.0, description: str = "",
                     provider: str = "openai", model_type: str = "text") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO ai_models 
                    (name, model_id, api_key, base_url, temperature, max_tokens,
                     top_p, frequency_penalty, presence_penalty, description, provider, model_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, model_id, api_key, base_url, temperature, max_tokens,
                     top_p, frequency_penalty, presence_penalty, description, provider, model_type)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_model(model_id: int, name: str, model_id_str: str, api_key: str, base_url: str,
                     temperature: float = 0.7, max_tokens: int = 4096,
                     top_p: float = 0.9, frequency_penalty: float = 0.0,
                     presence_penalty: float = 0.0, description: str = "",
                     provider: str = "openai", model_type: str = "text") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """UPDATE ai_models SET name=?, model_id=?, api_key=?, base_url=?, 
                    temperature=?, max_tokens=?, top_p=?, frequency_penalty=?, 
                    presence_penalty=?, description=?, provider=?, model_type=?, updated_at=datetime('now','localtime') 
                    WHERE id=?""",
                    (name, model_id_str, api_key, base_url, temperature, max_tokens,
                     top_p, frequency_penalty, presence_penalty, description, provider, model_type, model_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_model(model_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_models WHERE id=?", (model_id,))
        return True

    @staticmethod
    def set_default_model(model_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE ai_models SET is_default=0")
            conn.execute("UPDATE ai_models SET is_default=1 WHERE id=?", (model_id,))
        return True

    @staticmethod
    def toggle_model_status(model_id: int, status: int) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE ai_models SET status=? WHERE id=?", (status, model_id))
        return True

    @staticmethod
    def update_tokens(model_id: int, prompt_tokens: int, completion_tokens: int):
        total_tokens = prompt_tokens + completion_tokens
        with get_connection() as conn:
            conn.execute(
                """UPDATE ai_models SET 
                total_tokens = total_tokens + ?,
                prompt_tokens = prompt_tokens + ?,
                completion_tokens = completion_tokens + ?
                WHERE id=?""",
                (total_tokens, prompt_tokens, completion_tokens, model_id)
            )

    @staticmethod
    def get_token_stats():
        with get_connection() as conn:
            row = conn.execute(
                """SELECT SUM(total_tokens) as total, SUM(prompt_tokens) as prompt, 
                   SUM(completion_tokens) as completion, COUNT(*) as count 
                   FROM ai_models"""
            ).fetchone()
        return dict(row) if row else {"total": 0, "prompt": 0, "completion": 0, "count": 0}

    @staticmethod
    def get_type_stats():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT COALESCE(model_type, 'text') as model_type, COUNT(*) as count FROM ai_models GROUP BY COALESCE(model_type, 'text')"
            ).fetchall()
        stats = {"text": 0, "image": 0, "video": 0}
        for row in rows:
            stats[row["model_type"]] = row["count"]
        return stats


class AIModelService:
    @staticmethod
    def estimate_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
        try:
            encoding = tiktoken.encoding_for_model(model_name)
            return len(encoding.encode(text))
        except:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))

    @staticmethod
    def chat_completion(model_config: dict, messages: list, stream: bool = True):
        base_url = model_config["base_url"].rstrip('/')
        url = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config['api_key']}"
        }
        data = {
            "model": model_config["model_id"],
            "messages": messages,
            "temperature": model_config.get("temperature", 0.7),
            "max_tokens": model_config.get("max_tokens", 4096),
            "top_p": model_config.get("top_p", 0.9),
            "frequency_penalty": model_config.get("frequency_penalty", 0.0),
            "presence_penalty": model_config.get("presence_penalty", 0.0),
            "stream": stream
        }

        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context

        if not stream:
            response = requests.post(url, headers=headers, json=data, timeout=120, verify=False)
            if response.status_code != 200:
                try:
                    err_body = response.json()
                except Exception:
                    err_body = {"error": {"message": response.text or f"HTTP {response.status_code}"}}
                return err_body
            return response.json()

        def stream_generator():
            resp = requests.post(url, headers=headers, json=data, stream=True, timeout=120, verify=False)
            if resp.status_code != 200:
                try:
                    err_body = resp.json()
                    error_msg = err_body.get("error", {}).get("message", str(err_body))
                except Exception:
                    error_msg = resp.text or f"HTTP {resp.status_code}"
                yield {"error": True, "message": error_msg, "status_code": resp.status_code}
                return
            resp.encoding = "utf-8"
            for line in resp.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            yield json.loads(data_str)
                        except Exception:
                            continue

        return stream_generator()

    @staticmethod
    def _looks_like_html(response) -> bool:
        content_type = response.headers.get("Content-Type", "").lower()
        text = (response.text or "").lstrip().lower()
        return "text/html" in content_type or text.startswith("<!doctype html") or text.startswith("<html")

    @staticmethod
    def _multimodal_urls(model_config: dict, endpoint: str):
        base_url = model_config["base_url"].rstrip("/")
        urls = [f"{base_url}{endpoint}"]
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path.rstrip("/")
        if not path.endswith("/v1") and "/api/paas/" not in path:
            urls.append(f"{base_url}/v1{endpoint}")
        return urls

    @staticmethod
    def _friendly_html_error(url: str):
        parsed = urllib.parse.urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        return (
            "### 调用失败\n\n"
            "模型网关返回的是网页 HTML，不是模型 API JSON。通常是 Base URL 填成了管理后台首页地址。\n\n"
            f"- 当前请求地址：`{url}`\n"
            f"- New API / OpenAI 兼容网关通常应填写：`{root}/v1`\n"
            "- 然后生图接口会调用：`/images/generations`\n"
            "- 请确认模型类型选择为“生图”，模型 ID 填写该网关支持的 GLM 生图模型名。"
        )

    @staticmethod
    def _format_multimodal_payload(payload: dict, model_type: str):
        title = "图像生成结果" if model_type == "image" else "视频生成结果"
        data = payload.get("data") if isinstance(payload, dict) else None
        blocks = [f"### {title}"]

        if isinstance(data, list) and data:
            for index, item in enumerate(data, start=1):
                if not isinstance(item, dict):
                    continue
                url = item.get("url") or item.get("video_url") or item.get("output_url")
                b64_json = item.get("b64_json")
                if url:
                    if model_type == "image":
                        blocks.append(f"![生成图片 {index}]({url})")
                    else:
                        blocks.append(f"[生成视频 {index}]({url})")
                elif b64_json and model_type == "image":
                    blocks.append(f"![生成图片 {index}](data:image/png;base64,{b64_json})")

        blocks.append("```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```")
        return "\n\n".join(blocks)

    @staticmethod
    def generate_multimodal(model_config: dict, prompt: str):
        model_type = model_config.get("model_type", "text")
        endpoint = "/images/generations" if model_type == "image" else "/videos/generations"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {model_config['api_key']}"
        }
        data = {
            "model": model_config["model_id"],
            "prompt": prompt,
            "n": 1
        }

        last_response = None
        last_url = ""
        for url in AIModelService._multimodal_urls(model_config, endpoint):
            last_url = url
            response = requests.post(url, headers=headers, json=data, timeout=120, verify=False)
            last_response = response
            if AIModelService._looks_like_html(response):
                continue
            break

        if last_response is None:
            return {"success": False, "content": "### 调用失败\n\n未发起有效请求。"}

        response = last_response
        if AIModelService._looks_like_html(response):
            return {"success": False, "content": AIModelService._friendly_html_error(last_url)}

        try:
            payload = response.json()
        except Exception:
            payload = {"status_code": response.status_code, "text": response.text[:1000]}
            return {
                "success": False,
                "content": "### 调用失败\n\n接口没有返回 JSON。\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
            }

        if response.status_code >= 400 or payload.get("error"):
            return {
                "success": False,
                "content": "### 调用失败\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
            }

        return {
            "success": True,
            "content": AIModelService._format_multimodal_payload(payload, model_type)
        }

    @staticmethod
    def test_model(model_config: dict):
        messages = [
            {"role": "user", "content": "请输出一句简短的测试响应，如：测试成功"}
        ]
        try:
            result = AIModelService.chat_completion(model_config, messages, stream=False)
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                prompt_tokens = result.get("usage", {}).get("prompt_tokens", 0)
                completion_tokens = result.get("usage", {}).get("completion_tokens", 0)
                return {
                    "success": True,
                    "content": content,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens
                }
            if "error" in result:
                err = result["error"]
                if isinstance(err, dict):
                    error_msg = err.get("message", str(err))
                else:
                    error_msg = str(err)
                return {"success": False, "error": error_msg}
            return {"success": False, "error": "无响应数据"}
        except Exception as e:
            return {"success": False, "error": str(e)}
