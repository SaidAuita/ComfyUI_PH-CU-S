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

- Allows using ComfyUI as an image generation engine inside the Photoshop workflow.
- Supports masking, seed, CFG, and step control.
- Minimizes manual file exchange: the plugin and ComfyUI synchronize data automatically.
- Enables editing full-size high-resolution files by processing only the active region.
- Displays a default warning for exceeding 4 megapixels, which can be ignored.
- Aligns selections to Qwen and Flux 2 standard multiples of 112 and 64.
- Saves 6 presets for prompt, negative prompt, description, and SEED.
- If you need a re-generation with more steps using the same SEED, the seed can be fixed and custom STEP and CFG can be applied.
- Can be configured to use a custom URL for connecting to ComfyUI.
- Can set up ComfyUI on 1 computer (with good GPU and RAM) and connect to it over the local network from other computers, including tested with MAC (emulation in VMware, without video accelerator) / PC with integrated graphics. Detailed setup instructions and files are attached.
- All settings are preserved for the next Photoshop launch.
- Tested on a 3060 with 6 GB VRAM and 32 GB RAM. The Flux 2 Klein workflow works well.
- There are workflows for Qwen Edit 2511 and Flux 2 for more complex tasks if your hardware supports larger models. The Qwen Edit 2511 workflow was tested on a 3080Ti with 64 GB RAM. Flux2.dev was tested on a 3090 with 128 GB RAM.

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