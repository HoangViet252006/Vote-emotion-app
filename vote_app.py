import customtkinter as ctk
import json
import os
import sys
from PIL import Image
from customtkinter import CTkImage
import ctypes
from ctypes import wintypes
from collections import OrderedDict


LANG = "VI"


TEXTS = {
    "EN": {
        "title": "Emotion Voting App",
        "segment": "🎮 Scene:",
        "role": "🎭 Character Archetype",
        "external_emotion": "🧝 External Expression",
        "internal_emotion": "🧠 Internal Emotion",
        "prev": "⬅ Previous",
        "next": "Next ➡",
        "goto_first": "⏩ Go to First Unvoted Sample",
        "select_category": "Select Character Archetype Category",
        "select_role": "Select Specific Archetype Category",
        "image_not_found": "Image not found",
        "remaining_samples": "remaining"
    },
    "VI": {
        "title": "Ứng dụng bình chọn cảm xúc",
        "segment": "🎮 Trích đoạn:",
        "role": "🎭 Vai diễn",
        "external_emotion": "🧝 Cảm xúc bên ngoài",
        "internal_emotion": "🧠 Cảm xúc bên trong",
        "prev": "⬅ Trước",
        "next": "Tiếp ➡",
        "goto_first": "⏩ Đến mẫu chưa vote đầu tiên",
        "select_category": "Chọn loại vai",
        "select_role": "Chọn vai cụ thể",
        "image_not_found": "Không tìm thấy ảnh",
        "remaining_samples": "còn lại"
    }
}

def t(key):
    return TEXTS[LANG][key]


FONT_SIZE = 26
IMG_SIZE = 350

ROLE_CATEGORIES = {
    t("select_category"): [t("select_role")],
    "Đào": ["Đào chín", "Đào lệch", "Đào pha (ngang)"],
    "Kép": ["Kép chính", "Kép lệch", "Kép pha (ngang)"],
    "Hề": ["Hề áo trùng", "Hề áo ngắn"],
    "Lão": ["Lão tướng", "Lão say", "Lão mốc", "Lão thiện", "Lão ác", "Lão bộc", "Lão chài", "Lão tiều"],
    "Mụ": ["Mụ ác", "Mụ thiện", "Mụ mối"]
}

ALL_MERGED_LABELS_EN = ["Happiness", "Anger", "Love", "Hatred", "Sadness", "Fear"]
ALL_MERGED_LABELS_VI = ["Hỷ", "Nộ", "Ái", "Ố", "Ai", "Cụ"]
ALL_MERGED_LABELS = ALL_MERGED_LABELS_EN if LANG=="EN" else ALL_MERGED_LABELS_VI

# Mapping between EN <-> VI labels
LABEL_MAP_EN_VI = dict(zip(ALL_MERGED_LABELS_EN, ALL_MERGED_LABELS_VI))
LABEL_MAP_VI_EN = {v:k for k,v in LABEL_MAP_EN_VI.items()}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def extract_trich_doan_name(folder_path):
    return os.path.basename(os.path.dirname(folder_path))

output_root = resource_path('Output')
datas = []
for folder in os.listdir(output_root):
    folder_path = os.path.join(output_root, folder)
    json_path = os.path.join(folder_path, 'emotion_results.json')
    img_folder = os.path.join(folder_path, 'segment_images')
    if not (os.path.exists(json_path) and os.path.exists(img_folder)):
        continue
    with open(json_path, 'r', encoding='utf-8') as f:
        for item in json.load(f):
            pid = item["person_id"]
            paths = [os.path.join(img_folder, f"person_{pid}_frame_{item[k]}.jpg") for k in ['onset_frame_id', 'apex_frame_id', 'offset_frame_id']]
            item['image_folder'] = img_folder
            item['image_paths'] = paths
            datas.append(item)

# vote_output_path = os.path.join(os.getcwd(), 'votes_3000.json')
# roles_output_path = os.path.join(os.getcwd(), 'roles.json')

vote_output_path = os.path.join(os.getcwd(), 'votes_ver2.json')
roles_output_path = os.path.join(os.getcwd(), 'roles_ver2.json')
prev_votes = json.load(open(vote_output_path, 'r', encoding='utf-8')) if os.path.exists(vote_output_path) else []


# Kiểm tra chạy đơn instance
def ensure_single_instance(mutex_name="EmotionVoteAppMutex"):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    mutex = kernel32.CreateMutexW(None, wintypes.BOOL(True), wintypes.LPCWSTR(mutex_name))
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    ERROR_ALREADY_EXISTS = 183
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        print("Application already running, exiting...")
        sys.exit(0)


class EmotionVoteApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(t("title"))
        self.geometry("1350x700")
        self.scale = min(self.winfo_screenwidth() / 1920, self.winfo_screenheight() / 1080)

        self.index = 0
        self.votes = []
        self.role_memory = {}
        self.image_cache = OrderedDict()
        self.max_cache_size = 50
        self.index_order = [i for start in range(3) for i in range(start, len(datas), 3)]

        self.load_votes()
        self.create_widgets()
        self.display_sample()

    def scaled(self, value): return int(value * self.scale)

    # ----- roles -----
    def load_roles(self):
        self.role_memory = {}
        if not os.path.exists(roles_output_path):
            return
        with open(roles_output_path, 'r', encoding='utf-8') as f:
            raw_roles = json.load(f)
            for trich_doan, role_list in raw_roles.items():
                for role_entry in role_list:
                    pid = role_entry.get("id")
                    role_cat = role_entry.get("role_category")
                    role_name = role_entry.get("role_name")
                    if pid is not None and role_cat and role_name:
                        self.role_memory[(trich_doan, pid)] = (role_cat, role_name)

    def save_roles(self):
        output = {}
        for (trich_doan, pid), (role_cat, role_name) in self.role_memory.items():
            if trich_doan not in output:
                output[trich_doan] = []
            output[trich_doan].append({"id": pid, "role_category": role_cat, "role_name": role_name})
        with open(roles_output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    # ----- votes -----
    def load_votes(self):
        self.vote_index_map = {}
        self.load_roles()
        for i, data in enumerate(datas):
            vote = data.copy()
            prev = prev_votes[i] if i < len(prev_votes) else {}
            vote.update({
                'external_vote': prev.get('external_vote'),
                'internal_vote': prev.get('internal_vote')
            })
            key = (extract_trich_doan_name(vote['image_folder']), vote['person_id'])
            self.vote_index_map[key] = i
            if key in self.role_memory:
                vote['role_category'], vote['role_name'] = self.role_memory[key]
            else:
                vote['role_category'] = None
                vote['role_name'] = None
            self.votes.append(vote)

    def save_votes(self):
        output = []
        for v in self.votes:
            output.append({
                'person_id': v['person_id'],
                'onset_frame_id': v['onset_frame_id'],
                'apex_frame_id': v['apex_frame_id'],
                'offset_frame_id': v['offset_frame_id'],
                'external_vote': v.get('external_vote'),
                'internal_vote': v.get('internal_vote'),
                'trich_doan': extract_trich_doan_name(v['image_folder']),
                'emotion': v.get('emotion'),
                'emotion_merged': v.get('emotion_merged')
            })
        with open(vote_output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    # ----- image loader -----
    def load_ctk_image(self, path):
        if not os.path.exists(path):
            return None
        if path in self.image_cache:
            self.image_cache.move_to_end(path)
            return self.image_cache[path]

        size = self.scaled(IMG_SIZE), self.scaled(IMG_SIZE)
        img = Image.open(path).resize(size)
        ctk_img = CTkImage(light_image=img, dark_image=img, size=size)

        self.image_cache[path] = ctk_img
        self.image_cache.move_to_end(path)

        if len(self.image_cache) > self.max_cache_size:
            self.image_cache.popitem(last=False)

        return ctk_img

    # ----- display -----
    def display_sample(self):
        idx = self.index_order[self.index]
        data = self.votes[idx]
        pid = data['person_id']
        for key, lbl in zip(['onset_frame_id','apex_frame_id','offset_frame_id'],
                            [self.onset_img_label, self.apex_img_label, self.offset_img_label]):
            img_path = os.path.join(data['image_folder'], self.build_filename(data[key], pid))
            img = self.load_ctk_image(img_path)
            lbl.configure(image=img, text="" if img else t("image_not_found"))
            lbl.image = img

        # Handle EN <-> VI mapping for button highlighting
        external_vote = data.get('external_vote')
        internal_vote = data.get('internal_vote')
        if LANG == "VI":
            external_vote = LABEL_MAP_EN_VI.get(external_vote, external_vote)
            internal_vote = LABEL_MAP_EN_VI.get(internal_vote, internal_vote)

        for label, btn in self.external_buttons.items():
            if label == external_vote:
                btn.configure(fg_color="#388E3C", hover_color="#66BB6A")
            else:
                btn.configure(fg_color="#424242", hover_color="#616161")

        for label, btn in self.internal_buttons.items():
            if label == internal_vote:
                btn.configure(fg_color="#7E57C2", hover_color="#B39DDB")
            else:
                btn.configure(fg_color="#424242", hover_color="#616161")

        key = (extract_trich_doan_name(data['image_folder']), pid)
        cat, sub = self.role_memory.get(key, (None, None))
        if cat is None:
            self.category_var.set(t("select_category"))
            self.update_subroles(t("select_category"))
            self.subrole_var.set(t("select_role"))
        else:
            self.category_var.set(cat)
            self.update_subroles(cat)
            self.subrole_var.set(sub)

        rem = sum(1 for v in self.votes if not v.get('external_vote') or not v.get('internal_vote'))
        self.sample_counter.configure(text=f"Sample {self.index+1} / {len(datas)} — {rem} {t('remaining_samples')}")
        self.trich_doan_label.configure(text=f"{t('segment')} {extract_trich_doan_name(data['image_folder'])}")

    def build_filename(self, frame_id, pid):
        return f"person_{pid}_frame_{frame_id}.jpg"

    # ----- role vote -----
    def on_role_change(self):
        idx = self.index_order[self.index]
        item = self.votes[idx]
        role_cat = self.category_var.get()
        role_name = self.subrole_var.get()
        key = (extract_trich_doan_name(item['image_folder']), item['person_id'])
        self.role_memory[key] = (role_cat, role_name)
        self.votes[idx]['role_category'] = role_cat
        self.votes[idx]['role_name'] = role_name
        self.save_roles()

    def vote_emotion(self, vote_type, label):
        # Convert VI back to EN for storage if needed
        if LANG == "VI":
            label_to_store = LABEL_MAP_VI_EN.get(label, label)
        else:
            label_to_store = label

        idx = self.index_order[self.index]
        item = self.votes[idx]
        item[f"{vote_type}_vote"] = label_to_store
        self.on_role_change()
        self.save_votes()
        if item['external_vote'] and item['internal_vote']:
            self.next_sample()
        else:
            self.display_sample()

    # ----- navigation -----
    def next_sample(self):
        if self.index < len(self.index_order) - 1:
            self.index += 1
            self.display_sample()

    def prev_sample(self):
        if self.index > 0:
            self.index -= 1
            self.display_sample()

    def goto_first_unvoted(self):
        for i, idx in enumerate(self.index_order):
            vote = self.votes[idx]
            if not vote.get('external_vote') or not vote.get('internal_vote'):
                self.index = i
                break
        self.display_sample()

    # ----- role dropdown -----
    def update_subroles(self, category):
        self.subrole_dropdown.configure(values=ROLE_CATEGORIES.get(category, []))

    def on_category_dropdown_change(self, category):
        self.update_subroles(category)
        subs = ROLE_CATEGORIES[category]
        if self.subrole_var.get() not in subs:
            self.subrole_var.set(subs[0])
        self.on_role_change()

    # ----- vote buttons -----
    def build_vote_section(self, vote_type, title, button_dict):
        grp = ctk.CTkFrame(self)
        grp.pack(pady=self.scaled(20))
        ctk.CTkLabel(grp, text=title, font=("Arial", self.scaled(FONT_SIZE))).pack(pady=(0, self.scaled(10)))
        bf = ctk.CTkFrame(grp)
        bf.pack()
        for label in ALL_MERGED_LABELS:
            btn = ctk.CTkButton(
                bf, text=label, font=("Arial", self.scaled(FONT_SIZE)),
                fg_color="#424242", hover_color="#616161", text_color="white",
                command=lambda l=label: self.vote_emotion(vote_type, l)
            )
            btn.grid(row=0, column=len(button_dict), padx=self.scaled(5), pady=self.scaled(5))
            button_dict[label] = btn

    # ----- GUI layout -----
    def create_widgets(self):
        hdr = ctk.CTkFrame(self)
        hdr.pack(pady=self.scaled(10))
        self.trich_doan_label = ctk.CTkLabel(hdr, text=t("segment"), font=("Arial", self.scaled(FONT_SIZE+2)))
        self.trich_doan_label.pack()

        imgf = ctk.CTkFrame(self)
        imgf.pack(pady=self.scaled(10))
        self.onset_img_label = ctk.CTkLabel(imgf)
        self.apex_img_label = ctk.CTkLabel(imgf)
        self.offset_img_label = ctk.CTkLabel(imgf)
        for i, lbl in enumerate([self.onset_img_label, self.apex_img_label, self.offset_img_label]):
            lbl.grid(row=0, column=i, padx=self.scaled(10))

        rf = ctk.CTkFrame(self)
        rf.pack(pady=self.scaled(10))
        ctk.CTkLabel(rf, text=t("role"), font=("Arial", self.scaled(FONT_SIZE))).grid(row=0, column=0)
        self.category_var = ctk.StringVar(value=t("select_category"))
        self.subrole_var = ctk.StringVar(value=t("select_role"))
        self.category_dropdown = ctk.CTkOptionMenu(rf, values=list(ROLE_CATEGORIES), variable=self.category_var, command=self.on_category_dropdown_change)
        self.category_dropdown.grid(row=0, column=1, padx=self.scaled(10))
        self.subrole_dropdown = ctk.CTkOptionMenu(rf, values=[], variable=self.subrole_var, command=lambda _: self.on_role_change())
        self.subrole_dropdown.grid(row=0, column=2, padx=self.scaled(10))

        self.external_buttons = {}
        self.internal_buttons = {}
        self.build_vote_section("external", t("external_emotion"), self.external_buttons)
        self.build_vote_section("internal", t("internal_emotion"), self.internal_buttons)

        nf = ctk.CTkFrame(self)
        nf.pack(pady=self.scaled(20))
        ctk.CTkButton(nf, text=t("prev"), command=self.prev_sample, font=("Arial", self.scaled(FONT_SIZE))).grid(row=0, column=0)
        self.sample_counter = ctk.CTkLabel(nf, text="", font=("Arial", self.scaled(FONT_SIZE)), padx=self.scaled(10))
        self.sample_counter.grid(row=0, column=1)
        ctk.CTkButton(nf, text=t("next"), command=self.next_sample, font=("Arial", self.scaled(FONT_SIZE))).grid(row=0, column=2)
        ctk.CTkButton(self, text=t("goto_first"), command=self.goto_first_unvoted, font=("Arial", self.scaled(FONT_SIZE))).pack(pady=self.scaled(10))

if __name__ == "__main__":
    ensure_single_instance()
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = EmotionVoteApp()
    app.mainloop()

# pyinstaller --noconfirm --onefile --windowed --add-data "Output;Output" vote_app.py