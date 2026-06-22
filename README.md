# PH-CU-S for ComfyUI

**Official Website & Photoshop Plugin:** [ph-cu-s.com](https://www.ph-cu-s.com)

A set of nodes for integrating the Photoshop `PH-CU-S` plugin with `ComfyUI`.
Supported since version 2025.

## Node description

### 🎨 PH-CU-S Input

- Reads data from the `exchange` folder:
  - `canvas.png` — canvas
  - `mask.png` — mask
  - `prompt.txt` — prompt
  - `negative.txt` — negative prompt
  - `seed_fixed.txt` and `seed_in.txt` — seed
  - `step.txt` — step
  - `cfg.txt` — CFG
  - `extra_img_1.txt` — extra image 1
  - `extra_img_2.txt` — extra image 2
  - `extra_img_3.txt` — extra image 3
- Returns:
  - `Canvas` (IMAGE)
  - `Mask` (MASK)
  - `Prompt` (STRING)
  - `Negative Prompt` (STRING)
  - `Width`, `Height`, `Seed`, `Custom Step`, `CFG`
- Uses MD5 checking to trigger re-execution when `canvas.png` or `mask.png` changes.
- Screenshot: `images/input.png`

### 🎨 PH-CU-S Save Seed

- Takes a `seed` value and writes it to `exchange/seed_result.txt`.
- Passes the seed downstream in the graph.
- Useful when ComfyUI generates the seed and the Photoshop plugin needs the final value.
- Screenshot: `images/save_seed.png`

### 🎨 PH-CU-S Output

- Inherits functionality from `SaveImage`.
- Saves the final image to a temporary folder.
- After saving, sends an HTTP request to the local `PromptServer` to notify the plugin that rendering is complete:
  - `http://127.0.0.1:{port}/phcus/renderdone?filename={filename}`
- Screenshot: `images/out.png`

## Integration workflow

- `PH-CU-S Input` loads input data prepared by the Photoshop plugin.
- ComfyUI processes the image and passes the result to `PH-CU-S Output`.
- `PH-CU-S Save Seed` writes the final seed back for the plugin.
- The integration uses the `exchange` directory for file exchange and an HTTP signal for completion notification.

## Installation

1. Copy the `ComfyUI_PH-CU-S` folder into `ComfyUI/custom_nodes`.
2. Make sure it contains:
   - `nodes.py`
   - `server.py`
   - `exchange/`
   - `images/`
3. Start ComfyUI.
4. In the ComfyUI interface, find the `PH-CU-S` category and add the desired nodes.
5. Make sure the Photoshop `PH-CU-S` plugin is running and configured to use the `exchange` folder.

## Installation from GitHub

1. Clone the repository to your local computer:
   ```bash
   git clone https://github.com/SaidAuita/ComfyUI_PH-CU-S.git
   cd ComfyUI_PH-CU-S
   ```
2. Copy the `ComfyUI_PH-CU-S` folder into the ComfyUI `custom_nodes` directory:
   ```powershell
   Copy-Item -Path .\ComfyUI_PH-CU-S -Destination C:\path\to\ComfyUI\custom_nodes -Recurse
   ```
   If you want to copy only the contents of the folder, use:
   ```powershell
   Copy-Item -Path .\ComfyUI_PH-CU-S\* -Destination C:\path\to\ComfyUI\custom_nodes -Recurse
   ```
3. Start ComfyUI.
4. In the ComfyUI interface, find the `PH-CU-S` category and add the desired nodes.

## Output examples

Sample final images:

- `images/ph_00.jpg`
- `images/ph_01.jpg`
- `images/ph_02.jpg`

## Short description of the PH-CU-S plugin

PH-CU-S is an advanced UXP plugin for Adobe Photoshop that integrates ComfyUI directly into your Photoshop workflow. It allows you to run complex AI generation, inpainting, and outpainting tasks without leaving the canvas.

### Key Features & Capabilities:
- **Direct Photoshop Integration:** Work with familiar tools like layers, selections, and masks. The plugin automatically syncs the canvas, active selection, parameters, and generated outputs.
- **30 Prompt Slots (5 Sets x 6 Slots):** Store and organize up to 30 prompt configurations across 5 color-coded tabs.
  - Tab names can show compact labels (`SHOW_PROMPT_SET_NAMES` in `config.txt`).
  - Colors are fully customizable and can be associated with names (e.g., `#ffb0b0 - Pink` in `config.txt`).
- **Advanced Import & Export:**
  - **`6▼` and `30▼` Buttons:** Fast load prompts from a `.txt` file into the active set or sequentially across all 30 slots. Supports negative prompts (lines starting with `N:`) and slot descriptions (lines starting with `D:`). Lines starting with `#` are treated as comments and skipped.
  - **`30▲` Button:** Export all prompt configurations into a cleanly formatted text file.
- **AUTO & Loop (`∞`) Modes:**
  - **AUTO Mode:** Batch generate sequentially through slots 1–6 (or a custom count starting from the selected slot).
  - **Loop Mode (`∞`):** Enables seamless continuation of AUTO generation into the next color set when slot 6 is passed.
- **Smart Snap to Grid:** Automatically rounds selection sizes to grid multiples required by models (Flux x64, Qwen x112, Personal grid x8) to optimize generation quality. Automatically handles context padding on export when using brush selections.
- **Subpixel Alignment Safety:** Prevents subpixel shifts and alignment issues by temporarily clearing active Photoshop selections when placing generated images, followed by precise programmatic scaling and positioning.
- **Unified "Crop & Uncrop" Block:** A single, responsive block for expanding (uncrop) or shrinking (crop) the document canvas in selected directions, featuring interactive unit switchers (Millimeters, Inches, Pixels) and local storage persistence.
- **Local Network Support (PC / MAC):** Set up a high-performance ComfyUI server on one PC and connect multiple Photoshop clients (Windows & macOS) over a local network.
  - Features pre-configured setup scripts (`start_25H2_v2.bat` / `stop_25H2_v2.bat`) for easy sharing.
  - Direct local loading (`file://` URLs) bypasses caching and network delays on remote clients.
- **High-Resolution Editing:** Edit full-size high-res files by processing only the active region. Includes MAX_IMAGE_MP warnings (default 4MP) with direct options to downscale to 2/3/4 MP before sending.
- **Multi-language Interface:** Full localization support in 8 languages: English, Spanish, Japanese, German, Chinese, Portuguese, French, and Russian.
- **Robust License Backup:** Local license state backup (`~/.ph-cu-s/.license_state`) that bypasses UXP Node.js sandbox limitations on Windows and macOS.
- **Performance Optimized:** Tested and works great on standard consumer hardware (e.g., RTX 3060 with 6GB VRAM for Flux 2 Klein). Workflows for heavy models like Qwen Image Edit 2511 and Flux 2 Dev are fully supported for high-end systems.


## Screenshots

- ![PH-CU-S Input](images/input.jpg)
- ![PH-CU-S Save Seed](images/save_seed.jpg)
- ![PH-CU-S Output](images/out.jpg)

## Examples of work in Photoshop with the PH-CU-S plugin
- ![Example 01](images/01.jpg)
- ![Example 02](images/02.jpg)
- ![Example 03](images/03.jpg)
- ![Example 04](images/04.jpg)
- ![Example 05](images/05.jpg)
- ![Example 06](images/06.jpg)
- ![Example 07](images/07.jpg)
- ![Example 08](images/08.jpg)
- ![Example 09](images/09.jpg)
- ![Example 10](images/10.jpg)
- ![Example 11](images/11.jpg)