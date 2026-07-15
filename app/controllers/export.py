import os
import json
import html
from datetime import datetime

import tornado.web
from fpdf import FPDF

from app.controllers.base import BaseHandler
from app.models.conversations import ConversationRepository


class ExportHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        conversation_id = self.get_query_argument("conversation_id", None)
        if not conversation_id:
            self.set_status(400)
            self.write({"error": "缺少 conversation_id 参数"})
            return

        try:
            conversation_id = int(conversation_id)
        except ValueError:
            self.set_status(400)
            self.write({"error": "conversation_id 必须为数字"})
            return

        conv = ConversationRepository.get_conversation_by_id(conversation_id)
        if not conv:
            self.set_status(404)
            self.write({"error": "对话不存在"})
            return

        messages = ConversationRepository.get_messages(conversation_id)
        if not messages:
            self.set_status(404)
            self.write({"error": "该对话无消息内容"})
            return

        pdf_bytes = self._generate_pdf(conv, messages)

        filename = f"conversation_{conversation_id}.pdf"
        self.set_header("Content-Type", "application/pdf")
        self.set_header("Content-Disposition",
                        f'attachment; filename="{filename}"')
        self.write(pdf_bytes)

    def _generate_pdf(self, conv: dict, messages: list) -> bytes:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # Register Chinese font
        font_path = "C:/Windows/Fonts/simhei.ttf"
        if not os.path.exists(font_path):
            font_path = "C:/Windows/Fonts/msyh.ttc"
        if not os.path.exists(font_path):
            font_path = "C:/Windows/Fonts/simsun.ttc"

        if os.path.exists(font_path):
            pdf.add_font("CJK", "", font_path, uni=True)
            pdf.add_font("CJK", "B", font_path, uni=True)
            title_font = ("CJK", "B", 18)
            heading_font = ("CJK", "B", 12)
            body_font = ("CJK", "", 10)
            small_font = ("CJK", "", 8)
        else:
            title_font = ("Helvetica", "B", 18)
            heading_font = ("Helvetica", "B", 12)
            body_font = ("Helvetica", "", 10)
            small_font = ("Helvetica", "", 8)

        # Page width for layout calculations
        page_w = pdf.w - pdf.l_margin - pdf.r_margin

        # ---- Title ----
        pdf.set_font(*title_font)
        title = conv.get("title", "对话记录")
        pdf.multi_cell(page_w, 10, self._safe_text(title), align="C")
        pdf.ln(4)

        # ---- Export time ----
        pdf.set_font(*small_font)
        export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.set_text_color(128, 128, 128)
        pdf.cell(page_w, 6, f"导出时间: {export_time}", align="C")
        pdf.ln(8)

        # ---- Divider ----
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(6)

        # ---- Messages ----
        for i, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Skip empty messages
            if not content or not content.strip():
                continue

            # Role label
            pdf.set_font(*heading_font)
            if role == "user":
                pdf.set_text_color(59, 130, 246)  # Blue
                label = "用户"
            else:
                pdf.set_text_color(16, 185, 129)  # Green
                label = "AI 助手"

            # Check if we need a new page
            if pdf.get_y() > pdf.h - 50:
                pdf.add_page()

            pdf.cell(page_w, 7, f"▎{label}", align="L")
            pdf.ln(8)

            # Message content
            pdf.set_font(*body_font)
            pdf.set_text_color(51, 51, 51)  # Dark gray

            # Clean content for PDF rendering
            clean_content = self._safe_text(content)

            # Write content with proper line breaks
            pdf.multi_cell(page_w, 6, clean_content, align="L")
            pdf.ln(5)

        # ---- Footer ----
        pdf.set_font(*small_font)
        pdf.set_text_color(180, 180, 180)
        pdf.cell(page_w, 6, f"— 共 {len(messages)} 条消息 —", align="C")

        return bytes(pdf.output())

    @staticmethod
    def _safe_text(text: str) -> str:
        """Clean text for PDF rendering: unescape HTML entities and
        remove unsupported characters like emoji."""
        import re
        # Unescape any HTML entities
        text = html.unescape(text)
        # Remove emoji and symbols that SimHei font doesn't support:
        # - Emoticons (U+1F600-U+1F64F), Misc Symbols (U+2600-U+26FF)
        # - Dingbats (U+2700-U+27BF), Misc Symbols & Arrows (U+2B00-U+2BFF)
        # - Supplemental Symbols (U+1F300-U+1F5FF, U+1F680-U+1F6FF, U+1F900-U+1FAFF)
        # Keep: CJK, Latin, digits, common punctuation
        text = re.sub(r'[\U0001F000-\U0001FFFF]', '', text)
        text = re.sub(r'[☀-➿]', '', text)
        text = re.sub(r'[⬀-⯿]', '', text)
        text = re.sub(r'[︀-﻿]', '', text)
        return text
