# Pilot Data Experiment

Two-part memory experiment:
1. **PsychoPy encoding task** – image viewing with incidental judgment
2. **Flask web memory test** – recognition memory at 24 h / 48 h delay

---

## Folder structure

```
Pictures-task/
├── encoding_task.py          ← PsychoPy encoding session
├── stimuli/
│   ├── dataset_1/
│   │   ├── a/   ← 15 images (shown in Block 1 – no music)
│   │   ├── b/   ← 15 images (shown in Block 1 – no music)
│   │   ├── c/   ← 15 images (shown in Block 2 – music)
│   │   └── d/   ← 15 images (shown in Block 2 – music)
│   ├── dataset_2/  ...same structure...
│   ├── dataset_3/  ...
│   └── dataset_4/  ...
├── audio/
│   └── background_music.mp3  ← place your audio file here
├── data/
│   ├── encoding_*.csv        ← auto-saved by PsychoPy
│   └── memory_*.csv          ← auto-saved by web app
└── memory_test/
    ├── app.py
    ├── requirements.txt
    ├── templates/
    │   ├── setup.html
    │   ├── task.html
    │   └── done.html
    └── static/
        ├── style.css
        └── task.js
```

---

## Counterbalancing

| Role | Meaning |
|------|---------|
| X    | Participant group X → uses the dataset number assigned to X |
| Y    | Participant group Y → uses the dataset number assigned to Y |
| Z    | Participant group Z → uses the dataset number assigned to Z |
| W    | Participant group W → uses the dataset number assigned to W |

Each participant is assigned ONE condition (X/Y/Z/W).  
Each condition maps to ONE dataset (1–4).  
The mapping is entered at the start of both the PsychoPy session and the web memory test.

---

## Part 1 – PsychoPy Encoding Task

### Prerequisites

```bash
pip install psychopy
```

### Run

```bash
python encoding_task.py
```

### Setup dialog fields

| Field | Description |
|-------|-------------|
| Participant ID | Unique identifier (e.g. P01) |
| Condition | X / Y / Z / W (this participant's group) |
| Dataset for X | Dataset number (1–4) mapped to group X |
| Dataset for Y | Dataset number (1–4) mapped to group Y |
| Dataset for Z | Dataset number (1–4) mapped to group Z |
| Dataset for W | Dataset number (1–4) mapped to group W |

### Task flow

1. **Block 1** – No music  
   Subsets **a** + **b** from the participant's assigned dataset (30 images)  
   - Image displayed for **2 s**  
   - Washout: **3.5 – 6.5 s** (randomly sampled)  
   - **20 %** of trials: Hebrew judgment question appears during washout  
     → Press **1** = מתחיל (beginner) &nbsp;|&nbsp; **2** = מקצוען (professional)  
   - **80 %** of trials: fixation cross (+) only  

2. **Block 2** – Background music  
   Subsets **c** + **d** from the same dataset (30 images)  
   - Same timing and question probability as Block 1  
   - Background music (`audio/background_music.mp3`) plays throughout  

### Output CSV columns

`participant_id, condition, dataset, dataset_x, dataset_y, dataset_z, dataset_w,
block, trial, subset, image, image_onset_s, washout_dur_s,
question_shown, response, rt_s`

---

## Part 2 – Web Memory Test (24 h / 48 h)

### Prerequisites

```bash
cd memory_test
pip install -r requirements.txt
```

### Run

```bash
cd memory_test
python app.py
```

Then open **http://localhost:5000** in any browser.

### Setup form fields

| Field | Description |
|-------|-------------|
| Participant ID | Same ID used in PsychoPy session |
| Condition (group) | X / Y / Z / W (same as encoding) |
| Dataset for X/Y/Z/W | Same mapping entered during encoding |
| New foil dataset | A dataset the participant has **not** seen |
| Test delay | 24 h or 48 h |

### Task flow

The memory test mixes:
- **Seen** images: subsets **a** + **c** from the participant's original dataset  
  (subset a was shown in Block 1; subset c was shown in Block 2)
- **Unseen foils**: subsets **a** + **c** from the new foil dataset

Total: up to 60 images, presented in random order.

For each image, participants answer:
1. **האם ראית תמונה זו בעבר?** (Yes / No)
2. **עד כמה אתה/את בטוח/ה?** (1 = בטוח/ה שלא … 5 = בטוח/ה שכן)

### Output CSV columns

`participant_id, condition, test_delay, original_dataset, foil_dataset,
dataset_x, dataset_y, dataset_z, dataset_w,
trial, image_filename, subset, dataset_num, ground_truth,
recognition_response, certainty, rt_recognition_ms, rt_certainty_ms`

---

## Keyboard shortcuts (PsychoPy)

| Key | Action |
|-----|--------|
| 1   | Beginner (מתחיל) — during judgment question |
| 2   | Professional (מקצוען) — during judgment question |
| Escape | Quit session |
| Space | Advance through instructions |

---

## Notes

- Place the background music file at `audio/background_music.mp3`  
  (MP3, WAV, or OGG are all supported by PsychoPy).
- Image files can be JPG, PNG, BMP, or TIF.
- CSV files are saved with UTF-8 BOM encoding for easy opening in Excel.
