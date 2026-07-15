import os
import random
import time
import hashlib
import urllib.request
from pathlib import Path
from io import BytesIO

import torch
import numpy as np
from PIL import Image, ImageOps
import folder_paths
from nodes import SaveImage

PLUGIN_ROOT  = Path(os.path.dirname(os.path.abspath(__file__)))
EXCHANGE_DIR = PLUGIN_ROOT / "exchange"

__version__ = "3.61.00"
print(f"[PH-CU-S] Custom node version {__version__} loaded.")



def log_debug(msg):
    try:
        log_path = EXCHANGE_DIR / "debug_nodes.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception as e:
        print(f"Error writing to debug log: {e}")


class FileWatcher:
    """Tracks file content changes via MD5 to trigger node re-execution."""
    _cache: dict[str, str] = {}

    @classmethod
    def has_changed(cls, path: str) -> bool:
        try:
            with open(path, "rb") as fh:
                digest = hashlib.md5(fh.read()).hexdigest()
        except OSError:
            log_debug(f"has_changed OSError for {os.path.basename(path)}")
            return True
        prev = cls._cache.get(path)
        cls._cache[path] = digest
        changed = prev != digest
        log_debug(f"has_changed {os.path.basename(path)}: prev={prev[:8] if prev else 'None'} curr={digest[:8]} changed={changed}")
        return changed


def _read_text(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback


def _read_image(path: Path) -> Image.Image:
    try:
        raw = path.read_bytes()
        img = Image.open(BytesIO(raw))
        img.verify()
        return Image.open(BytesIO(raw))
    except Exception as exc:
        print(f"[PH-CU-S] Cannot read {path.name}: {exc}")
        return Image.new("RGB", (256, 256), 0)


def _image_to_tensor(img: Image.Image):
    arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr)[None]


def _mask_to_tensor(img: Image.Image):
    img = ImageOps.exif_transpose(img)
    if "A" in img.getbands():
        bg = Image.new("RGBA", img.size, "BLACK")
        bg.paste(img, mask=img)
        grey = bg.convert("L")
    else:
        grey = img.convert("L")
    arr = np.array(grey, dtype=np.float32) / 255.0
    arr[arr <= 1.0 / 255.0] = 0.0
    return torch.from_numpy(arr)


def _load_extra_image(idx: int, client_id: str = "") -> torch.Tensor:
    suffix = f"_{client_id}" if client_id else ""
    # 1. Search directly in EXCHANGE_DIR first (from 3.60.14)
    direct_path = EXCHANGE_DIR / f"extra_img_{idx}{suffix}.png"
    if direct_path.exists():
        print(f"[PH-CU-S] Images slot {idx}: found direct → {direct_path}")
        return _image_to_tensor(_read_image(direct_path))
    elif client_id:
        direct_path_fallback = EXCHANGE_DIR / f"extra_img_{idx}.png"
        if direct_path_fallback.exists():
            print(f"[PH-CU-S] Images slot {idx}: found fallback direct → {direct_path_fallback}")
            return _image_to_tensor(_read_image(direct_path_fallback))

    # 2. Fallback to txt file
    txt_path = EXCHANGE_DIR / f"extra_img_{idx}{suffix}.txt"
    if not txt_path.exists() and client_id:
        txt_path = EXCHANGE_DIR / f"extra_img_{idx}.txt"
    raw_path = _read_text(txt_path, "").strip()
    if not raw_path:
        print(f"[PH-CU-S] Images slot {idx}: empty")
        return torch.zeros(1, 1, 1, 3)

    # 3. Try raw path as absolute path
    img_path = Path(raw_path)
    if img_path.exists():
        print(f"[PH-CU-S] Images slot {idx}: found absolute → {img_path}")
        return _image_to_tensor(_read_image(img_path))

    # 4. Resolve path relative to exchange folder (from 3.60.11)
    # If absolute path does not match (macOS/Windows virtual environments mismatch)
    import os
    base_name = os.path.basename(raw_path.replace("\\", "/"))
    exchange_fallback = EXCHANGE_DIR / base_name
    if exchange_fallback.exists():
        print(f"[PH-CU-S] Images slot {idx}: resolved via exchange → {exchange_fallback}")
        return _image_to_tensor(_read_image(exchange_fallback))

    # 5. Resolve relative paths if ComfyUI is launched via bat-files (from 3.60.13)
    # The relative path from the txt might contain "ComfyUI/" prefix or not.
    # Try resolving relative to ComfyUI root directory.
    # PLUGIN_ROOT is ComfyUI/custom_nodes/ComfyUI_PH-CU-S.
    # So ComfyUI root is PLUGIN_ROOT.parent.parent
    comfy_root = PLUGIN_ROOT.parent.parent
    
    # Strip "ComfyUI/" prefix from raw_path if present, because we are already relative to comfy_root
    normalized_rel = raw_path.replace("\\", "/")
    if normalized_rel.startswith("ComfyUI/"):
        normalized_rel = normalized_rel[len("ComfyUI/"):]
    elif normalized_rel.startswith("/ComfyUI/"):
        normalized_rel = normalized_rel[len("/ComfyUI/"):]
        
    rel_path = comfy_root / normalized_rel
    if rel_path.exists():
        print(f"[PH-CU-S] Images slot {idx}: resolved relative to ComfyUI root → {rel_path}")
        return _image_to_tensor(_read_image(rel_path))
        
    # Also try resolving relative to PLUGIN_ROOT's parent (custom_nodes) or PLUGIN_ROOT itself
    if "custom_nodes/" in normalized_rel:
        custom_node_rel = normalized_rel.split("custom_nodes/", 1)[1]
        resolved_custom = PLUGIN_ROOT / custom_node_rel
        if resolved_custom.exists():
            print(f"[PH-CU-S] Images slot {idx}: resolved relative to custom_nodes → {resolved_custom}")
            return _image_to_tensor(_read_image(resolved_custom))

    print(f"[PH-CU-S] Images slot {idx}: not found → {raw_path}")
    return torch.zeros(1, 1, 1, 3)


class PHCUSInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "client_id": ("STRING", {"default": ""})
            }
        }

    RETURN_TYPES  = ("IMAGE", "MASK", "STRING", "STRING", "INT", "INT", "INT", "INT", "FLOAT",
                     "IMAGE", "IMAGE", "IMAGE", "INT")
    RETURN_NAMES  = ("Canvas", "Mask", "Prompt", "Negative Prompt",
                     "Width", "Height", "Seed", "Custom Step", "CFG",
                     "Image 1", "Image 2", "Image 3", "Zoom")
    FUNCTION  = "execute"
    CATEGORY  = "PH-CU-S"

    def execute(self, client_id=""):
        log_debug(f"execute() called with client_id={client_id!r}")
        ex = EXCHANGE_DIR
        suffix = f"_{client_id}" if client_id else ""

        canvas_path = ex / f"canvas{suffix}.png"
        if not canvas_path.exists() and client_id:
            canvas_path = ex / "canvas.png"
            
        for _ in range(5):
            if canvas_path.exists():
                break
            time.sleep(0.5)

        canvas_img = _read_image(canvas_path)
        w, h = canvas_img.size
        canvas_t = _image_to_tensor(canvas_img)
        
        mask_path = ex / f"mask{suffix}.png"
        if not mask_path.exists() and client_id:
            mask_path = ex / "mask.png"
        mask_t   = _mask_to_tensor(_read_image(mask_path))

        prompt_path = ex / f"prompt{suffix}.txt"
        if not prompt_path.exists() and client_id:
            prompt_path = ex / "prompt.txt"
        prompt   = _read_text(prompt_path)
        log_debug(f"execute() prompt path: {prompt_path.name}, content: {prompt!r}")
        
        neg_path = ex / f"negative{suffix}.txt"
        if not neg_path.exists() and client_id:
            neg_path = ex / "negative.txt"
        negative = _read_text(neg_path)
        log_debug(f"execute() negative path: {neg_path.name}, content: {negative!r}")

        seed_fixed_path = ex / f"seed_fixed{suffix}.txt"
        if not seed_fixed_path.exists() and client_id:
            seed_fixed_path = ex / "seed_fixed.txt"
        seed_fixed = int(_read_text(seed_fixed_path, "0"))
        
        seed_in_path = ex / f"seed_in{suffix}.txt"
        if not seed_in_path.exists() and client_id:
            seed_in_path = ex / "seed_in.txt"
        seed_val   = int(_read_text(seed_in_path, "0"))

        if seed_fixed == 0:
            seed_val = random.randint(0, 2**32 - 1)
            print(f"[PH-CU-S] Random seed: {seed_val}")
        else:
            print(f"[PH-CU-S] Fixed seed: {seed_val}")
        log_debug(f"execute() seed_fixed={seed_fixed}, seed_val={seed_val}")

        step_path = ex / f"step{suffix}.txt"
        if not step_path.exists() and client_id:
            step_path = ex / "step.txt"
        custom_step = int(_read_text(step_path, "0"))
        
        cfg_path = ex / f"cfg{suffix}.txt"
        if not cfg_path.exists() and client_id:
            cfg_path = ex / "cfg.txt"
        cfg_val     = float(_read_text(cfg_path, "1.0"))
        print(f"[PH-CU-S] Step={custom_step}  CFG={cfg_val}")

        zoom_path = ex / f"zoom_resolution{suffix}.txt"
        if not zoom_path.exists() and client_id:
            zoom_path = ex / "zoom_resolution.txt"
        zoom_res = int(_read_text(zoom_path, "0"))
        print(f"[PH-CU-S] Zoom={zoom_res}")

        return (canvas_t, mask_t.unsqueeze(0), prompt, negative,
                w, h, seed_val, custom_step, cfg_val,
                _load_extra_image(1, client_id), _load_extra_image(2, client_id), _load_extra_image(3, client_id),
                zoom_res)

    @classmethod
    def IS_CHANGED(cls, client_id=""):
        log_debug(f"IS_CHANGED() called with client_id={client_id!r}")
        suffix = f"_{client_id}" if client_id else ""
        
        def check_file(name):
            p = EXCHANGE_DIR / f"{name}{suffix}.txt"
            if not p.exists() and client_id:
                p = EXCHANGE_DIR / f"{name}.txt"
            return str(p)
            
        def check_img(name):
            p = EXCHANGE_DIR / f"{name}{suffix}.png"
            if not p.exists() and client_id:
                p = EXCHANGE_DIR / f"{name}.png"
            return str(p)

        # Update all caches to avoid stale checks in case we need them,
        # but always return NaN to force ComfyUI to re-execute this node
        # so that it reads fresh values for every prompt queue run.
        FileWatcher.has_changed(check_img("canvas"))
        FileWatcher.has_changed(check_img("mask"))
        FileWatcher.has_changed(check_file("prompt"))
        FileWatcher.has_changed(check_file("negative"))
        FileWatcher.has_changed(check_file("seed_in"))
        FileWatcher.has_changed(check_file("seed_fixed"))
        FileWatcher.has_changed(check_file("step"))
        FileWatcher.has_changed(check_file("cfg"))
        for i in range(1, 4):
            FileWatcher.has_changed(check_file(f"extra_img_{i}"))
        FileWatcher.has_changed(check_file("zoom_resolution"))

        log_debug("IS_CHANGED() returning NaN (always execute)")
        return float("NaN")


class PHCUSSaveSeed:
    """Writes the resolved seed to seed_result.txt and passes it downstream."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**32 - 1}),
                "client_id": ("STRING", {"default": ""})
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    FUNCTION     = "execute"
    CATEGORY     = "PH-CU-S"
    OUTPUT_NODE  = True

    def execute(self, seed: int, client_id=""):
        suffix = f"_{client_id}" if client_id else ""
        dest = EXCHANGE_DIR / f"seed_result{suffix}.txt"
        try:
            dest.write_text(str(seed), encoding="utf-8")
            print(f"[PH-CU-S] seed_result{suffix}.txt ← {seed}")
        except OSError as exc:
            print(f"[PH-CU-S] Cannot write seed_result.txt: {exc}")
        return (seed,)


class PHCUSOutput(SaveImage):

    def __init__(self):
        self.output_dir     = folder_paths.get_temp_directory()
        self.type           = "temp"
        self.prefix_append  = "_phcus_"
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "output_image": ("IMAGE",),
                "client_id": ("STRING", {"default": ""})
            },
            "hidden":   {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    FUNCTION    = "execute"
    CATEGORY    = "PH-CU-S"
    OUTPUT_NODE = True

    def _signal_ready(self, filename: str, client_id=""):
        try:
            from server import PromptServer
            port = PromptServer.instance.port
            url  = f"http://127.0.0.1:{port}/phcus/renderdone?filename={filename}&client_id={client_id}"
            with urllib.request.urlopen(urllib.request.Request(url)) as resp:
                return resp.read().decode()
        except Exception as exc:
            print(f"[PH-CU-S] Signal failed: {exc}")

    def execute(self, output_image: torch.Tensor, client_id="",
                filename_prefix="PF_OUT", prompt=None, extra_pnginfo=None):
        height = int(output_image.shape[1])
        width = int(output_image.shape[2])
        suffix = f"_{client_id}" if client_id else ""
        width_path = EXCHANGE_DIR / f"output_width{suffix}.txt"
        height_path = EXCHANGE_DIR / f"output_height{suffix}.txt"

        if width > 0 and height > 0:
            try:
                width_path.write_text(str(width), encoding="utf-8")
                height_path.write_text(str(height), encoding="utf-8")
                print(f"[PH-CU-S] output_width{suffix}.txt ← {width}")
                print(f"[PH-CU-S] output_height{suffix}.txt ← {height}")
            except OSError as exc:
                print(f"[PH-CU-S] Cannot write output dimensions: {exc}")
        else:
            for path in (width_path, height_path):
                if path.exists():
                    try:
                        path.unlink()
                    except OSError:
                        pass

        result   = self.save_images(output_image, filename_prefix, prompt, extra_pnginfo)
        filename = result["ui"]["images"][0]["filename"]
        
        log_debug(f"PHCUSOutput.execute: filename={filename}")
        log_debug(f"PHCUSOutput.execute: self.output_dir={self.output_dir}")

        # Copy the result image to exchange folder for the plugin to read
        temp_path = Path(self.output_dir) / filename
        log_debug(f"PHCUSOutput.execute: temp_path={temp_path} (exists={temp_path.exists()})")

        result_path = EXCHANGE_DIR / f"result{suffix}.png"
        try:
            import shutil
            shutil.copy2(temp_path, result_path)
            print(f"[PH-CU-S] result{suffix}.png ← {filename} ({width}x{height})")
        except Exception as exc:
            print(f"[PH-CU-S] Cannot copy result to exchange: {exc}")

        # --- Save copy to disk based on output settings ---
        try:
            def read_param(name, default=""):
                p_path = EXCHANGE_DIR / f"{name}{suffix}.txt"
                if p_path.exists():
                    try:
                        return p_path.read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
                p_path_nosuf = EXCHANGE_DIR / f"{name}.txt"
                if p_path_nosuf.exists():
                    try:
                        return p_path_nosuf.read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
                return default

            output_mode = read_param("output_mode", "photoshop").lower()
            
            # Determine base output dir
            base_out_dir_str = read_param("output_dir", "")
            log_debug(f"PHCUSOutput.execute: output_mode={output_mode}, base_out_dir_str={base_out_dir_str}")
            if not base_out_dir_str:
                base_out_dir = Path(folder_paths.get_output_directory())
            else:
                base_out_dir = Path(base_out_dir_str)
            log_debug(f"PHCUSOutput.execute: base_out_dir={base_out_dir}")

            if output_mode in ("folder", "all"):
                output_folder_date = read_param("output_folder_date", "false").lower() == "true"
                log_debug(f"PHCUSOutput.execute: output_folder_date={output_folder_date}")

                # Clean up name to be a safe directory/file name
                def make_safe(name):
                    for char in r'<>:"/\|?*':
                        name = name.replace(char, '-')
                    return name.strip()

                target_subfolder = ""
                if output_folder_date:
                    target_subfolder = time.strftime("%Y-%m-%d")

                final_out_dir = base_out_dir
                if target_subfolder:
                    final_out_dir = final_out_dir / target_subfolder
                log_debug(f"PHCUSOutput.execute: final_out_dir={final_out_dir}")

                try:
                    final_out_dir.mkdir(parents=True, exist_ok=True)
                    log_debug(f"PHCUSOutput.execute: Created/verified final_out_dir={final_out_dir}")
                except Exception as exc:
                    log_debug(f"PHCUSOutput.execute: Cannot create output directory {final_out_dir}: {exc}")
                    final_out_dir = base_out_dir



                # Build filename
                job_name = make_safe(read_param("job_name", "Workflow"))
                slot_info = read_param("slot_info", "")
                
                seed_used = ""
                seed_file = EXCHANGE_DIR / f"seed_result{suffix}.txt"
                if seed_file.exists():
                    try:
                        seed_used = seed_file.read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
                if not seed_used:
                    seed_used = read_param("seed_in", "")

                slot_part = ""
                if slot_info:
                    slot_part = f" {slot_info.replace(':', '-')}"
                seed_part = f" s-{seed_used}" if seed_used else ""
                out_filename = f"{job_name}{slot_part}{seed_part}.png"

                out_filename = make_safe(out_filename)
                if not out_filename.lower().endswith(".png"):
                    out_filename += ".png"

                stem = Path(out_filename).stem
                counter = 1
                final_file_path = final_out_dir / out_filename
                while final_file_path.exists():
                    final_file_path = final_out_dir / f"{stem}_{counter}.png"
                    counter += 1

                log_debug(f"PHCUSOutput.execute: target file path={final_file_path}")
                try:
                    import shutil
                    shutil.copy2(temp_path, final_file_path)
                    log_debug(f"[PH-CU-S] Saved copy to disk: {final_file_path}")
                except Exception as exc:
                    log_debug(f"[PH-CU-S] Failed to save copy to disk: {exc}")
            else:
                # photoshop mode: write the base_out_dir to last_saved_folder file
                last_saved_folder_file = EXCHANGE_DIR / f"last_saved_folder{suffix}.txt"
                try:
                    last_saved_folder_file.write_text(str(base_out_dir), encoding="utf-8")
                except Exception as exc:
                    pass
        except Exception as exc:
            print(f"[PH-CU-S] Error in output settings execution: {exc}")

        self._signal_ready(filename, client_id)
        return result


NODE_CLASS_MAPPINGS = {
    "PHCUSInput":    PHCUSInput,
    "PHCUSOutput":   PHCUSOutput,
    "PHCUSSaveSeed": PHCUSSaveSeed,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PHCUSInput":    "🎨 PH-CU-S Input",
    "PHCUSOutput":   "🎨 PH-CU-S Output",
    "PHCUSSaveSeed": "🎨 PH-CU-S Save Seed",
}
