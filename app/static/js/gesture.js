class GestureRecognizer {
    constructor(videoElement, canvasElement, statusElement, onGestureDetected) {
        this.videoElement = videoElement;
        this.canvasElement = canvasElement;
        this.statusElement = statusElement;
        this.onGestureDetected = onGestureDetected;
        this.hands = null;
        this.isRunning = false;
        this.lastGesture = null;
        this.lastGestureTime = 0;
        this.cooldownTime = 3000;
        this.ctx = canvasElement.getContext('2d');
    }

    async init() {
        try {
            this.hands = new Hands({locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
            }});

            this.hands.setOptions({
                maxNumHands: 1,
                modelComplexity: 1,
                minDetectionConfidence: 0.5,
                minTrackingConfidence: 0.5
            });

            this.hands.onResults(this.onResults.bind(this));

            const stream = await navigator.mediaDevices.getUserMedia({video: true});
            this.videoElement.srcObject = stream;
            this.videoElement.onloadedmetadata = () => {
                this.videoElement.play();
                this.isRunning = true;
                this.processVideo();
            };
        } catch (error) {
            console.error('摄像头启动失败:', error);
            if (this.statusElement) {
                this.statusElement.textContent = '摄像头启动失败，请检查权限';
                this.statusElement.style.color = '#dc2626';
            }
        }
    }

    stop() {
        this.isRunning = false;
        if (this.videoElement.srcObject) {
            this.videoElement.srcObject.getTracks().forEach(track => track.stop());
        }
        if (this.hands) {
            this.hands.close();
        }
    }

    resetGesture() {
        this.lastGesture = null;
        this.lastGestureTime = 0;
    }

    async processVideo() {
        if (!this.isRunning) return;
        
        if (this.hands) {
            await this.hands.send({image: this.videoElement});
        }
        
        requestAnimationFrame(() => this.processVideo());
    }

    onResults(results) {
        this.ctx.save();
        this.ctx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
        this.ctx.drawImage(results.image, 0, 0, this.canvasElement.width, this.canvasElement.height);

        if (results.multiHandLandmarks) {
            for (const landmarks of results.multiHandLandmarks) {
                drawConnectors(this.ctx, landmarks, HAND_CONNECTIONS, {color: '#2563eb', lineWidth: 2});
                drawLandmarks(this.ctx, landmarks, {color: '#1d4ed8', lineWidth: 1});
                
                const gesture = this.recognizeGesture(landmarks);
                this.updateStatus(gesture);
                
                if (gesture && gesture !== 'none') {
                    this.handleGesture(gesture);
                }
            }
        } else {
            this.updateStatus('none');
        }
        this.ctx.restore();
    }

    recognizeGesture(landmarks) {
        const fingers = this.getFingerStates(landmarks);
        
        if (fingers.index && fingers.middle && !fingers.ring && !fingers.pinky && !fingers.thumb) {
            return 'scissors';
        }
        
        if (!fingers.index && !fingers.middle && !fingers.ring && !fingers.pinky && !fingers.thumb) {
            return 'fist';
        }
        
        if (fingers.index && fingers.middle && fingers.ring && fingers.pinky && fingers.thumb) {
            return 'palm';
        }
        
        if (fingers.index && !fingers.middle && !fingers.ring && !fingers.pinky && !fingers.thumb) {
            return 'thumbs_up';
        }
        
        return 'none';
    }

    getFingerStates(landmarks) {
        const isFingerExtended = (tipIdx, pipIdx) => {
            return landmarks[tipIdx].y < landmarks[pipIdx].y;
        };

        const isThumbExtended = () => {
            return landmarks[4].y < landmarks[3].y;
        };

        return {
            thumb: isThumbExtended(),
            index: isFingerExtended(8, 6),
            middle: isFingerExtended(12, 10),
            ring: isFingerExtended(16, 14),
            pinky: isFingerExtended(20, 18)
        };
    }

    updateStatus(gesture) {
        if (!this.statusElement) return;
        
        const gestureNames = {
            'scissors': '✌️ 剪刀手 - 查询天气',
            'fist': '✊ 握拳 - 播放音乐',
            'palm': '🖐️ 手掌 - 获取新闻',
            'thumbs_up': '☝️ 伸出食指 - 停止生成',
            'none': '请做出手势'
        };
        
        this.statusElement.textContent = gestureNames[gesture] || '请做出手势';
        
        if (gesture !== 'none') {
            this.statusElement.style.color = '#2563eb';
        } else {
            this.statusElement.style.color = '#9ca3af';
        }
    }

    handleGesture(gesture) {
        const now = Date.now();
        
        if (gesture === 'thumbs_up') {
            if (this.onGestureDetected && this.lastGesture !== 'thumbs_up') {
                this.onGestureDetected(gesture);
            }
            this.lastGesture = gesture;
            this.lastGestureTime = now;
            return;
        }
        
        if (this.lastGesture === gesture) {
            if (now - this.lastGestureTime >= this.cooldownTime) {
                if (this.onGestureDetected) {
                    this.onGestureDetected(gesture);
                }
                this.lastGestureTime = now;
            }
        } else {
            this.lastGesture = gesture;
            this.lastGestureTime = now;
        }
    }
}