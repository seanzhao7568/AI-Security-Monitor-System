import os
import cv2
import time
import threading
import numpy as np
import requests

from config import *
from monitor.buffers import HitBuffer
from monitor.helpers import expand_roi, dbfs_from_audio

try:
    import pygame
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

try:
    import torch
    from ultralytics import YOLO
    YOLO_OK = True
except Exception:
    torch = None
    YOLO = None
    YOLO_OK = False


class SecurityMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.noise_lock = threading.Lock()

        self.running = False
        self.thread = None
        self.audio_thread = None
        self.cap = None

        self.current_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        self.toggles = dict(DEFAULT_TOGGLES)

        self.status = {
            "danger": False,
            "warning": False,
            "safe": True,
            "level": 0,

            "risk_score": 0,
            "risk_reasons": [],
            "danger_candidate": False,
            "warn_candidate": False,

            "close_area_ratio": None,
            "close_trigger": False,

            "weapon_trigger": False,
            "weapon_hits": 0,
            "weapon_window": WEAPON_WINDOW,
            "weapon_best_name": None,
            "weapon_best_conf": 0.0,

            "aggro_trigger": False,
            "aggro_motion": None,

            "noise_dbfs": None,
            "noise_floor": None,
            "noise_trigger": False,

            "reason": None,
            "timestamp": time.time(),
            "running": False,
            "fps": 0.0,

            "telegram_token": os.getenv("TG_BOT_TOKEN", "").strip(),
            "telegram_chat_id": os.getenv("TG_CHAT_ID", "").strip(),
            "toggles": dict(self.toggles),
        }

        self.last_frame_time = time.time()
        self.fps = 0.0

        self.danger_counter = 0
        self.safe_counter = 0
        self.is_alerting = False

        self.alert_latched = False

        self.last_telegram_time = 0.0
        self.last_telegram_reason_key = ""

        self.weapon_hits_buf = HitBuffer(window=WEAPON_WINDOW)
        self.prev_best_area = None

        self.aggro_buf = HitBuffer(window=AGGRO_WINDOW)
        self.prev_kps = None
        self.prev_t = None
        self.last_pose_score = None
        self.pose_frame_idx = 0

        self.noise_dbfs = None
        self.noise_floor = None
        self.noise_trigger = False
        self.noise_danger = False
        self.noise_warn_buf = HitBuffer(window=NOISE_CONFIRM_WINDOW)
        self.noise_danger_buf = HitBuffer(window=NOISE_CONFIRM_WINDOW)

        self.prev_small_gray = None

        self.cuda_ok = bool(YOLO_OK and torch.cuda.is_available())
        self.device = 0 if self.cuda_ok else "cpu"

        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_model_file = os.path.join(self.project_root, BASE_MODEL_PATH)
        self.pose_model_file = os.path.join(self.project_root, POSE_MODEL_PATH)
        self.weapon_model_file = os.path.join(self.project_root, WEAPON_MODEL_PATH)
        self.alert_wav_file = os.path.join(self.project_root, ALERT_WAV_PATH)

        self.model = None
        self.weapon_model = None
        self.pose_model = None

        if YOLO_OK:
            self._load_models()

        if PYGAME_OK:
            try:
                pygame.mixer.init()
                self.alert_sound = pygame.mixer.Sound(self.alert_wav_file) if os.path.exists(self.alert_wav_file) else None
            except Exception:
                self.alert_sound = None
        else:
            self.alert_sound = None

    def _load_models(self):
        try:
            self.model = YOLO(self.base_model_file)
            print("[Model] base loaded:", self.base_model_file)
        except Exception as e:
            print("[Model] base load failed:", e)
            self.model = None

        try:
            if os.path.exists(self.weapon_model_file):
                self.weapon_model = YOLO(self.weapon_model_file)
                print("[Weapon] loaded:", self.weapon_model_file)
            else:
                print("[Weapon] file not found:", self.weapon_model_file)
        except Exception as e:
            print("[Weapon] load failed:", e)
            self.weapon_model = None

        try:
            if os.path.exists(self.pose_model_file):
                self.pose_model = YOLO(self.pose_model_file)
                print("[Pose] loaded:", self.pose_model_file)
            else:
                print("[Pose] file not found:", self.pose_model_file)
        except Exception as e:
            print("[Pose] load failed:", e)
            self.pose_model = None

        try:
            dummy = np.zeros((IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
            if self.model is not None:
                _ = self.model.predict(dummy, imgsz=IMG_SIZE, conf=0.01, device=self.device, half=self.cuda_ok, verbose=False)
            if self.weapon_model is not None:
                _ = self.weapon_model.predict(dummy, imgsz=IMG_SIZE, conf=0.01, device=self.device, half=self.cuda_ok, verbose=False)
            if self.pose_model is not None:
                _ = self.pose_model.predict(dummy, imgsz=IMG_SIZE, conf=0.01, device=self.device, half=self.cuda_ok, verbose=False)
            print("[Warmup] done")
        except Exception as e:
            print("[Warmup] skipped:", e)

    def update_telegram(self, token, chat_id):
        with self.lock:
            self.status["telegram_token"] = str(token).strip()
            self.status["telegram_chat_id"] = str(chat_id).strip()

    def update_toggles(self, data):
        with self.lock:
            for key in self.toggles.keys():
                if key in data:
                    self.toggles[key] = bool(data[key])
            self.status["toggles"] = dict(self.toggles)

    def _telegram_values(self):
        with self.lock:
            return self.status["telegram_token"], self.status["telegram_chat_id"]

    def _stop_alert_sound(self):
        if self.alert_sound is not None:
            try:
                self.alert_sound.stop()
            except Exception:
                pass

    def _play_alert_once(self):
        if self.alert_sound is not None:
            try:
                self.alert_sound.play()
            except Exception:
                pass

    def _send_telegram_photo(self, img_bgr, caption: str, reason_key: str = ""):
        token, chat_id = self._telegram_values()

        if not token or not chat_id:
            return False, "尚未設定 Bot Token 或 Chat ID"

        now = time.time()
        if reason_key == self.last_telegram_reason_key and (now - self.last_telegram_time <= TELEGRAM_COOLDOWN):
            return False, "Telegram 冷卻中"

        draw = img_bgr.copy()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        margin = 12

        (tw, th), baseline = cv2.getTextSize(ts, font, font_scale, thickness)
        h, w = draw.shape[:2]
        x = max(10, w - tw - margin)
        y = max(th + 10, h - margin)

        cv2.rectangle(draw, (x - 8, y - th - 8), (x + tw + 8, y + baseline + 6), (0, 0, 0), -1)
        cv2.putText(draw, ts, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        ok, buf = cv2.imencode(".jpg", draw, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            return False, "影像編碼失敗"

        url = f"https://api.telegram.org/bot{token}/sendPhoto"

        try:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": ("frame.jpg", buf.tobytes(), "image/jpeg")},
                timeout=10,
            )

            if r.status_code == 200:
                self.last_telegram_time = now
                self.last_telegram_reason_key = reason_key
                return True, "Telegram 傳送成功"

            return False, f"HTTP {r.status_code} - {r.text}"

        except Exception as e:
            return False, f"Telegram 發送失敗: {e}"

    def test_telegram(self):
        with self.frame_lock:
            frame = self.current_frame.copy()
        return self._send_telegram_photo(frame, "測試成功：AI 監控 Web App 已連線", reason_key="TEST")

    def _kpt_ok(self, conf_arr, idx, thr):
        return (conf_arr is not None) and (float(conf_arr[idx]) >= thr)

    def _dist(self, a, b):
        return float(np.linalg.norm(a - b))

    def _safe_scale(self, kps, conf, min_conf):
        if self._kpt_ok(conf, 5, min_conf) and self._kpt_ok(conf, 6, min_conf):
            s = self._dist(kps[5], kps[6])
            return s if s > 1e-3 else 1.0
        if self._kpt_ok(conf, 11, min_conf) and self._kpt_ok(conf, 12, min_conf):
            s = self._dist(kps[11], kps[12])
            return s if s > 1e-3 else 1.0
        return 1.0

    def _cam_shake_estimate(self, raw_bgr):
        try:
            small = cv2.resize(raw_bgr, (160, 90))
            g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if self.prev_small_gray is None:
                self.prev_small_gray = g
                return 0.0
            prevg = self.prev_small_gray
            self.prev_small_gray = g
            diff = cv2.absdiff(prevg, g)
            diff = cv2.GaussianBlur(diff, (5, 5), 0)
            return float(np.mean(diff))
        except Exception:
            return 0.0

    def _audio_worker(self):
        try:
            import sounddevice as sd
        except Exception as e:
            print("[Noise] sounddevice 不可用:", e)
            return

        block = int(NOISE_SAMPLE_RATE * NOISE_BLOCK_SEC)

        def callback(indata, frames, time_info, status):
            x = indata[:, 0].astype(np.float32)
            db = dbfs_from_audio(x)

            with self.noise_lock:
                self.noise_dbfs = db

                if self.noise_floor is None:
                    self.noise_floor = db

                delta = db - self.noise_floor
                warn_hit = 1 if delta >= NOISE_WARN_DELTA_DB else 0
                danger_hit = 1 if delta >= NOISE_DANGER_DELTA_DB else 0

                if not danger_hit:
                    self.noise_floor = (1 - NOISE_FLOOR_ALPHA) * self.noise_floor + NOISE_FLOOR_ALPHA * db

                self.noise_warn_buf.push(warn_hit)
                self.noise_danger_buf.push(danger_hit)

                self.noise_trigger = (self.noise_warn_buf.sum() >= NOISE_WARN_HIT_FRAMES)
                self.noise_danger = (self.noise_danger_buf.sum() >= NOISE_DANGER_HIT_FRAMES)

        print("[Noise] Audio stream start")
        try:
            with sd.InputStream(
                channels=1,
                samplerate=NOISE_SAMPLE_RATE,
                blocksize=block,
                callback=callback
            ):
                while True:
                    if not self.running:
                        break
                    time.sleep(0.2)
        except Exception as e:
            print("[Noise] audio worker stopped:", e)

    def _fuse_risk(
        self,
        close_warn: bool,
        close_danger: bool,
        weapon_trigger: bool,
        aggro_trigger: bool,
        local_noise_warn: bool,
        local_noise_danger: bool,
        toggles: dict
    ):
        reasons = []
        score = 0

        if toggles.get("weapon_detection", True) and weapon_trigger:
            reasons.append("WEAPON")

        if toggles.get("aggro_detection", True) and aggro_trigger:
            reasons.append("AGGRESSIVE")

        if toggles.get("noise_detection", True) and local_noise_danger:
            reasons.append("LOUD_NOISE")

        if toggles.get("person_close", True) and close_danger:
            reasons.append("PERSON_DANGER")

        if len(reasons) > 0:
            score = 100

            if weapon_trigger and aggro_trigger:
                score += 20
            if weapon_trigger and local_noise_danger:
                score += 15
            if aggro_trigger and local_noise_danger:
                score += 10
            if close_danger and weapon_trigger:
                score += 10
            if close_danger and aggro_trigger:
                score += 10

            main_reason = reasons[0]
            return score, reasons, False, True, main_reason

        if toggles.get("person_close", True) and close_warn:
            reasons.append("PERSON_WARN")
            score += 40

        if toggles.get("noise_detection", True) and local_noise_warn:
            reasons.append("NOISE_WARN")
            score += 20

        danger_candidate = score >= RISK_DANGER_SCORE
        warn_candidate = (score >= RISK_WARNING_SCORE) and not danger_candidate
        main_reason = reasons[0] if reasons else None

        return score, reasons, warn_candidate, danger_candidate, main_reason

    def start(self):
        if self.running:
            return
        self.running = True

        self.danger_counter = 0
        self.safe_counter = 0
        self.is_alerting = False
        self.alert_latched = False
        self.weapon_hits_buf.reset()
        self.aggro_buf.reset()
        self.prev_best_area = None
        self.prev_kps = None
        self.prev_t = None
        self.last_pose_score = None
        self.prev_small_gray = None

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        with self.lock:
            if self.toggles.get("noise_detection", True):
                self.audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
                self.audio_thread.start()

    def stop(self):
        self.running = False
        self._stop_alert_sound()

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        with self.lock:
            self.status["running"] = False

    def _run(self):
        self.cap = cv2.VideoCapture(CAM_INDEX)
        if not self.cap.isOpened():
            with self.lock:
                self.status["running"] = False
                self.status["reason"] = "CAMERA_OPEN_FAILED"
            self.running = False
            return

        while self.running:
            now_loop = time.time()
            dt = max(1e-6, now_loop - self.last_frame_time)
            self.fps = 1.0 / dt
            self.last_frame_time = now_loop

            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.03)
                continue

            raw = frame.copy()
            height, width = frame.shape[:2]

            with self.lock:
                toggles = dict(self.toggles)

            weapon_score = 0
            weapon_trigger = False
            weapon_best_conf = 0.0
            weapon_best_name = None

            aggro_trigger = False
            pose_score = None

            local_dbfs = None
            local_floor = None
            local_noise_warn = False
            local_noise_danger = False

            best_person = None
            best_person_area = 0
            best_person_ratio = None
            close_warn = False
            close_danger = False

            if toggles.get("person_close", True) and self.model is not None:
                try:
                    results = self.model.predict(
                        raw,
                        imgsz=IMG_SIZE,
                        conf=0.35,
                        device=self.device,
                        half=self.cuda_ok,
                        verbose=False
                    )[0]

                    boxes = results.boxes.xyxy
                    cls = results.boxes.cls

                    for i, box in enumerate(boxes):
                        class_id = int(cls[i])
                        label = self.model.names[class_id]
                        if label != CLOSE_LABEL:
                            continue

                        x1, y1, x2, y2 = map(int, box)
                        bw, bh = x2 - x1, y2 - y1
                        area = bw * bh

                        if area > best_person_area:
                            best_person_area = area
                            best_person = (x1, y1, x2, y2)
                            best_person_ratio = area / float(width * height)

                    if best_person is not None and best_person_ratio is not None:
                        if best_person_ratio > DANGER_THRESHOLD:
                            close_danger = True
                        elif best_person_ratio > DANGER_THRESHOLD * WARN_RATIO:
                            close_warn = True

                except Exception as e:
                    print("[Detect] person error:", e)

            if (
                toggles.get("weapon_detection", True)
                and self.weapon_model is not None
                and best_person is not None
            ):
                x1, y1, x2, y2 = best_person
                rx1, ry1, rx2, ry2 = expand_roi(x1, y1, x2, y2, width, height, ROI_EXPAND)

                roi_full = raw[ry1:ry2, rx1:rx2]
                if roi_full is None or roi_full.size == 0:
                    roi = roi_full
                else:
                    if WEAPON_ROI_LOWER_ONLY:
                        h_roi = roi_full.shape[0]
                        roi = roi_full[int(h_roi * WEAPON_ROI_LOWER_START):, :]
                    else:
                        roi = roi_full

                hit = 0
                if roi is not None and roi.size != 0:
                    try:
                        wr = self.weapon_model.predict(
                            roi,
                            imgsz=IMG_SIZE,
                            conf=WEAPON_CONF,
                            iou=WEAPON_IOU,
                            device=self.device,
                            half=self.cuda_ok,
                            verbose=False
                        )[0]

                        if wr.boxes is not None and len(wr.boxes) > 0:
                            xyxy = wr.boxes.xyxy.cpu().numpy()
                            confs = wr.boxes.conf.cpu().numpy() if hasattr(wr.boxes, "conf") else np.ones((len(xyxy),), dtype=np.float32)
                            clss = wr.boxes.cls.cpu().numpy().astype(int) if hasattr(wr.boxes, "cls") else np.zeros((len(xyxy),), dtype=int)

                            idxs = np.argsort(-confs)
                            if WEAPON_TOP1_ONLY:
                                idxs = idxs[:1]

                            for j in idxs:
                                ax1, ay1, ax2, ay2 = xyxy[j]
                                c = float(confs[j])
                                cid = int(clss[j])
                                name = self.weapon_model.names.get(cid, str(cid)) if hasattr(self.weapon_model, "names") else str(cid)

                                a = (ax2 - ax1) * (ay2 - ay1)
                                bw = max(1.0, (ax2 - ax1))
                                bh = max(1.0, (ay2 - ay1))
                                ar = max(bw / bh, bh / bw)

                                if name not in WEAPON_ALLOWED_NAMES:
                                    continue
                                if a < MIN_WEAPON_BOX_AREA:
                                    continue
                                if c < WEAPON_MIN_CONF_HIT:
                                    continue
                                if not (WEAPON_MIN_BOX_AR <= ar <= WEAPON_MAX_BOX_AR):
                                    continue

                                hit = 1
                                weapon_best_conf = c
                                weapon_best_name = name
                                break
                    except Exception as e:
                        print("[Detect] weapon error:", e)

                self.weapon_hits_buf.push(hit)
                weapon_score = self.weapon_hits_buf.sum()
                weapon_trigger = (weapon_score >= WEAPON_HIT_FRAMES)

                cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 255, 0), 2)
                cv2.putText(
                    frame,
                    f"weapon hits {weapon_score}/{WEAPON_WINDOW}",
                    (rx1, max(0, ry1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
                )
                cv2.putText(
                    frame,
                    f"weapon best={weapon_best_name} conf={weapon_best_conf:.2f}",
                    (rx1, max(0, ry1 - 28)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
                )

            if best_person is not None:
                if self.prev_best_area is None:
                    self.prev_best_area = best_person_area
                else:
                    if best_person_area < self.prev_best_area * 0.5 or best_person_area > self.prev_best_area * 1.8:
                        self.weapon_hits_buf.reset()
                    self.prev_best_area = best_person_area
            else:
                self.weapon_hits_buf.reset()
                self.prev_best_area = None

            self.pose_frame_idx += 1
            cam_shake = self._cam_shake_estimate(raw)

            if (
                toggles.get("aggro_detection", True)
                and self.pose_model is not None
                and best_person is not None
                and best_person_area >= AGGRO_MIN_PERSON_AREA
            ):
                if (self.pose_frame_idx % POSE_RUN_EVERY_N_FRAMES) == 0:
                    x1, y1, x2, y2 = best_person
                    rx1, ry1, rx2, ry2 = expand_roi(x1, y1, x2, y2, width, height, 0.08)
                    roi = raw[ry1:ry2, rx1:rx2]

                    hit = 0
                    wrist_speed = ankle_speed = jerk = arm_ext = leg_ext = 0.0

                    if roi is not None and roi.size != 0:
                        try:
                            pr = self.pose_model.predict(
                                roi,
                                imgsz=IMG_SIZE,
                                conf=POSE_CONF,
                                iou=POSE_IOU,
                                device=self.device,
                                half=self.cuda_ok,
                                verbose=False
                            )[0]

                            if pr.keypoints is not None and len(pr.keypoints) > 0:
                                kps_xy = pr.keypoints.xy
                                kps_cf = pr.keypoints.conf if hasattr(pr.keypoints, "conf") else None

                                kps = kps_xy[0].cpu().numpy()
                                conf = kps_cf[0].cpu().numpy() if kps_cf is not None else None

                                now_t = time.time()
                                dt_pose = 1e-3 if self.prev_t is None else max(1e-3, now_t - self.prev_t)
                                scale = self._safe_scale(kps, conf, POSE_MIN_KPT_CONF)

                                if self.prev_kps is not None and self.prev_kps.shape == kps.shape:
                                    ws = []
                                    if self._kpt_ok(conf, 9, POSE_MIN_KPT_CONF):
                                        ws.append(self._dist(kps[9], self.prev_kps[9]) / dt_pose / scale)
                                    if self._kpt_ok(conf, 10, POSE_MIN_KPT_CONF):
                                        ws.append(self._dist(kps[10], self.prev_kps[10]) / dt_pose / scale)
                                    wrist_speed = max(ws) if ws else 0.0

                                    aks = []
                                    if self._kpt_ok(conf, 15, POSE_MIN_KPT_CONF):
                                        aks.append(self._dist(kps[15], self.prev_kps[15]) / dt_pose / scale)
                                    if self._kpt_ok(conf, 16, POSE_MIN_KPT_CONF):
                                        aks.append(self._dist(kps[16], self.prev_kps[16]) / dt_pose / scale)
                                    ankle_speed = max(aks) if aks else 0.0

                                arm_ext_l = arm_ext_r = 1.0
                                if self._kpt_ok(conf, 5, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 7, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 9, POSE_MIN_KPT_CONF):
                                    den = max(1e-3, self._dist(kps[5], kps[7]))
                                    arm_ext_l = self._dist(kps[5], kps[9]) / den
                                if self._kpt_ok(conf, 6, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 8, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 10, POSE_MIN_KPT_CONF):
                                    den = max(1e-3, self._dist(kps[6], kps[8]))
                                    arm_ext_r = self._dist(kps[6], kps[10]) / den
                                arm_ext = max(arm_ext_l, arm_ext_r)

                                leg_ext_l = leg_ext_r = 1.0
                                if self._kpt_ok(conf, 11, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 13, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 15, POSE_MIN_KPT_CONF):
                                    den = max(1e-3, self._dist(kps[11], kps[13]))
                                    leg_ext_l = self._dist(kps[11], kps[15]) / den
                                if self._kpt_ok(conf, 12, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 14, POSE_MIN_KPT_CONF) and self._kpt_ok(conf, 16, POSE_MIN_KPT_CONF):
                                    den = max(1e-3, self._dist(kps[12], kps[14]))
                                    leg_ext_r = self._dist(kps[12], kps[16]) / den
                                leg_ext = max(leg_ext_l, leg_ext_r)

                                cur_score = float(max(wrist_speed, ankle_speed))
                                jerk = 0.0 if self.last_pose_score is None else abs(cur_score - self.last_pose_score)

                                if cam_shake < CAM_SHAKE_THR:
                                    punch_like = (
                                        wrist_speed >= POSE_WRIST_SPEED_THR and
                                        arm_ext >= POSE_ARM_EXT_THR and
                                        jerk >= POSE_JERK_THR
                                    )
                                    kick_like = (
                                        ankle_speed >= POSE_ANKLE_SPEED_THR and
                                        leg_ext >= POSE_LEG_EXT_THR and
                                        jerk >= POSE_JERK_THR
                                    )
                                    hit = 1 if (punch_like or kick_like) else 0
                                else:
                                    hit = 0

                                self.last_pose_score = cur_score
                                pose_score = cur_score
                                self.prev_kps = kps
                                self.prev_t = now_t

                                cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (180, 255, 180), 2)
                                cv2.putText(
                                    frame,
                                    f"POSE ws={wrist_speed:.2f} as={ankle_speed:.2f} jerk={jerk:.2f} arm={arm_ext:.2f} leg={leg_ext:.2f} hit={hit} sum={self.aggro_buf.sum()}/{AGGRO_WINDOW} shake={cam_shake:.1f}",
                                    (rx1, min(height - 10, ry2 + 20)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 255, 180), 2
                                )
                        except Exception as e:
                            print("[Detect] pose error:", e)

                    self.aggro_buf.push(hit)
                    aggro_trigger = (self.aggro_buf.sum() >= AGGRO_HIT_FRAMES)
            else:
                self.aggro_buf.reset()

            if toggles.get("noise_detection", True):
                with self.noise_lock:
                    local_dbfs = self.noise_dbfs
                    local_floor = self.noise_floor
                    local_noise_warn = bool(self.noise_trigger)
                    local_noise_danger = bool(self.noise_danger)

            risk_score, risk_reasons, warn_candidate, danger_candidate, main_reason = self._fuse_risk(
                close_warn=close_warn,
                close_danger=close_danger,
                weapon_trigger=weapon_trigger,
                aggro_trigger=aggro_trigger,
                local_noise_warn=local_noise_warn,
                local_noise_danger=local_noise_danger,
                toggles=toggles
            )

            instant_danger = (
                (toggles.get("weapon_detection", True) and weapon_trigger) or
                (toggles.get("aggro_detection", True) and aggro_trigger) or
                (toggles.get("noise_detection", True) and local_noise_danger) or
                (toggles.get("person_close", True) and close_danger)
            )

            if instant_danger:
                self.danger_counter = DANGER_FRAMES
                self.safe_counter = 0
            elif danger_candidate:
                self.danger_counter += 1
                self.safe_counter = 0
            else:
                self.safe_counter += 1
                self.danger_counter = 0

            entered_danger_this_frame = False

            if toggles.get("alert_system", True) and self.danger_counter >= DANGER_FRAMES:
                if not self.is_alerting:
                    self.is_alerting = True
                    entered_danger_this_frame = True

                if entered_danger_this_frame and not self.alert_latched:
                    self._play_alert_once()
                    self.alert_latched = True

                caption = f"⚠️ DANGER\nscore={risk_score}\nreasons={', '.join(risk_reasons) if risk_reasons else 'UNKNOWN'}"
                if best_person_ratio is not None:
                    caption += f"\nperson_ratio={best_person_ratio:.3f}"
                if weapon_trigger:
                    caption += f"\nweapon={weapon_best_name} conf={weapon_best_conf:.2f} hits={weapon_score}/{WEAPON_WINDOW}"
                if aggro_trigger and pose_score is not None:
                    caption += f"\naggro_motion={pose_score:.2f}"
                if (local_dbfs is not None) and (local_floor is not None):
                    caption += f"\nnoise={local_dbfs:.1f} dBFS floor={local_floor:.1f}"

                reason_key = "|".join(sorted(risk_reasons))
                self._send_telegram_photo(frame, caption, reason_key=reason_key)
            else:
                self.is_alerting = False

            if self.safe_counter >= SAFE_FRAMES:
                self._stop_alert_sound()
                self.is_alerting = False
                self.alert_latched = False

            if best_person is not None:
                x1, y1, x2, y2 = best_person
                color = (0, 255, 0)
                if danger_candidate or instant_danger:
                    color = (0, 0, 255)
                elif warn_candidate:
                    color = (0, 255, 255)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

                person_text = f"person {best_person_ratio:.2f}"
                if close_danger:
                    person_text += " DANGER_CLOSE"
                elif close_warn:
                    person_text += " WARN_CLOSE"

                cv2.putText(
                    frame,
                    person_text,
                    (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
                )

            if self.is_alerting:
                alpha = 0.35 + 0.15 * np.sin(time.time() * 10)
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 255), -1)
                frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
                cv2.putText(frame, "DANGER", (50, 80),
                            cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 3)
            elif warn_candidate:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (width, height), (0, 255, 255), -1)
                frame = cv2.addWeighted(overlay, 0.22, frame, 0.78, 0)
                cv2.putText(frame, "WARNING", (50, 80),
                            cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 0, 0), 3)

            cv2.putText(frame, f"FPS={self.fps:.1f}", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"risk_score={risk_score}", (20, height - 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"main_reason={main_reason}", (20, height - 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"DANGER_FRAMES={self.danger_counter}/{DANGER_FRAMES}", (20, height - 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"weapon_score={weapon_score}/{WEAPON_WINDOW}", (20, height - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            if local_dbfs is not None and local_floor is not None:
                cv2.putText(frame, f"noise={local_dbfs:.1f}dBFS floor={local_floor:.1f}",
                            (20, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            else:
                cv2.putText(frame, "noise=NA", (20, height - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            y_text = 30
            for rr in risk_reasons[:5]:
                cv2.putText(frame, rr, (width - 280, y_text),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                y_text += 28

            with self.frame_lock:
                self.current_frame = frame.copy()

            with self.lock:
                self.status.update({
                    "danger": bool(self.is_alerting),
                    "warning": bool(warn_candidate),
                    "safe": not self.is_alerting and not warn_candidate,
                    "level": 2 if self.is_alerting else (1 if warn_candidate else 0),

                    "risk_score": int(risk_score),
                    "risk_reasons": list(risk_reasons),
                    "danger_candidate": bool(danger_candidate or instant_danger),
                    "warn_candidate": bool(warn_candidate),

                    "close_area_ratio": float(best_person_ratio) if best_person_ratio is not None else None,
                    "close_trigger": bool(close_danger or close_warn),

                    "weapon_trigger": bool(weapon_trigger),
                    "weapon_hits": int(weapon_score),
                    "weapon_window": WEAPON_WINDOW,
                    "weapon_best_name": weapon_best_name,
                    "weapon_best_conf": float(weapon_best_conf),

                    "aggro_trigger": bool(aggro_trigger),
                    "aggro_motion": float(pose_score) if pose_score is not None else None,

                    "noise_dbfs": float(local_dbfs) if local_dbfs is not None else None,
                    "noise_floor": float(local_floor) if local_floor is not None else None,
                    "noise_trigger": bool(local_noise_warn or local_noise_danger),

                    "reason": main_reason,
                    "timestamp": time.time(),
                    "running": True,
                    "fps": float(self.fps),
                    "toggles": dict(toggles),
                })

        self._stop_alert_sound()
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        with self.lock:
            self.status["running"] = False

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def get_jpeg(self):
        with self.frame_lock:
            frame = self.current_frame.copy()

        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return buf.tobytes()
