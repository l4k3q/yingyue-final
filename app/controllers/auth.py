import json
import base64
import numpy as np
import tornado.web
import cv2
import os

from app.controllers.base import BaseHandler
from app.models.user import UserRepository


class LoginHandler(BaseHandler):
    def get(self):
        self.render("login.html", title="用户登录", error=None)

    def post(self):
        username = self.get_body_argument("username", "")
        password = self.get_body_argument("password", "")
        if not username or not password:
            self.set_status(400)
            return self.render("login.html", title="用户登录", error="请输入用户名和密码")

        if not UserRepository.verify_user(username, password):
            self.set_status(401)
            return self.render("login.html", title="用户登录", error="用户名或密码不正确")

        self.set_secure_cookie("username", username)
        self.redirect("/index")


class LogoutHandler(BaseHandler):
    def post(self):
        self.clear_cookie("username")
        self.redirect("/")


class RegisterHandler(BaseHandler):
    def get(self):
        self.render("register.html", title="用户注册", error=None, success=None)

    def post(self):
        username = self.get_body_argument("username", "")
        password = self.get_body_argument("password", "")
        confirm_password = self.get_body_argument("confirm_password", "")

        if not username or not password:
            self.set_status(400)
            return self.render("register.html", title="用户注册", error="请输入用户名和密码")

        if password != confirm_password:
            self.set_status(400)
            return self.render("register.html", title="用户注册", error="两次输入的密码不一致")

        if not UserRepository.create_user(username, password):
            self.set_status(400)
            return self.render("register.html", title="用户注册", error="用户名已存在")

        self.redirect("/")


class FaceRegisterHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def post(self):
        try:
            data = json.loads(self.request.body)
            username = data.get("username", "")
            password = data.get("password", "")
            image = data.get("image", "")

            if not username or not password:
                self.write(json.dumps({"success": False, "message": "请输入用户名和密码"}))
                return

            if not UserRepository.verify_user(username, password):
                self.write(json.dumps({"success": False, "message": "用户名或密码错误"}))
                return

            if not image:
                self.write(json.dumps({"success": False, "message": "请开启摄像头并捕获人脸图像"}))
                return

            try:
                if image.startswith("data:image"):
                    image = image.split(",")[1]
                image_bytes = base64.b64decode(image)

                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is None:
                    self.write(json.dumps({"success": False, "message": "图片解码失败"}))
                    return

                h, w = img.shape[:2]
                face_size = min(w, h) // 2
                x = (w - face_size) // 2
                y = (h - face_size) // 2
                
                face_roi = img[y:y+face_size, x:x+face_size]
                face_roi = cv2.resize(face_roi, (100, 100))

                face_embedding = json.dumps(face_roi.flatten().tolist())
                UserRepository.update_face_embedding(username, face_embedding)

                self.write(json.dumps({"success": True, "message": "人脸注册成功"}))
            except Exception as e:
                print(f"[FaceAuth] 人脸注册异常: {e}", flush=True)
                self.write(json.dumps({"success": False, "message": f"注册失败: {str(e)}"}))
        except json.JSONDecodeError:
            self.write(json.dumps({"success": False, "message": "请求格式错误"}))


class FaceLoginHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def post(self):
        try:
            data = json.loads(self.request.body)
            image = data.get("image", "")

            if not image:
                self.write(json.dumps({"success": False, "message": "请开启摄像头并捕获人脸图像"}))
                return

            try:
                if image.startswith("data:image"):
                    image = image.split(",")[1]
                image_bytes = base64.b64decode(image)

                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is None:
                    self.write(json.dumps({"success": False, "message": "图片解码失败"}))
                    return

                h, w = img.shape[:2]
                face_size = min(w, h) // 2
                x = (w - face_size) // 2
                y = (h - face_size) // 2
                
                face_roi = img[y:y+face_size, x:x+face_size]
                face_roi = cv2.resize(face_roi, (100, 100))
                current_embedding = face_roi.flatten()

                users = UserRepository.get_users_with_face_embedding()

                best_match = None
                best_score = float('inf')

                for user in users:
                    face_embedding_str = user.get("face_embedding")
                    if not face_embedding_str:
                        continue
                    try:
                        stored_embedding = np.array(json.loads(face_embedding_str), dtype=np.float32)
                        if stored_embedding.shape != current_embedding.shape:
                            continue
                        diff = np.abs(current_embedding - stored_embedding)
                        score = np.mean(diff)
                        if score < best_score:
                            best_score = score
                            best_match = user
                    except Exception as e:
                        continue

                if best_match and best_score < 45:
                    self.set_secure_cookie("username", best_match["username"])
                    self.write(json.dumps({"success": True, "username": best_match["username"]}))
                else:
                    self.write(json.dumps({"success": False, "message": "未识别到已注册的人脸"}))
            except Exception as e:
                print(f"[FaceAuth] 人脸登录异常: {e}", flush=True)
                self.write(json.dumps({"success": False, "message": f"登录失败: {str(e)}"}))
        except json.JSONDecodeError:
            self.write(json.dumps({"success": False, "message": "请求格式错误"}))