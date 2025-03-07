# %%
import math
import pickle
import os
import threading
import subprocess
import time

import asyncio
import argparse
from websockets.server import serve
import websockets
import nest_asyncio

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["PYTHONUTF8"] = "1"

# %%
from diffusers import StableDiffusionImg2ImgPipeline
import torch
import numpy as np
import gc
from PIL import Image
import shutil

process_killed_event = threading.Event()
max_attempts = 20
current_time = time.gmtime()

import argparse

parser = argparse.ArgumentParser(description="Script that accepts command line arguments")
parser.add_argument("-i", "--iterations", type=int, default=10,
                    help="Number of iterations to perform (default: 10)")

parser.add_argument("-m", "--model", type=str, default="instant-ngp",
                    help="Model to use (default: instant-ngp) ")

parser.add_argument("-s", "--steps", type=int, default=3500,
                    help="Number of steps (default: 3500)")

parser.add_argument("-d", "--not_tokenized", action="store_true",
                    help="If the prompt is not tokenized (default: False if arg not specified)")

args = parser.parse_args()

max_iterations = args.iterations
model_type = args.model
steps = args.steps
not_tokenized = args.not_tokenized

print("-------------------------------------")
print(f"Max iterations: {max_iterations}")
print(f"Model type: {model_type}")
print(f"Number of steps: {steps}")
print(f"Not Tokenized: {not_tokenized}")
print("-------------------------------------")


class TrainElement:
    def __init__(self, prospective: str, filename: str, init_image_name: str):
        self.prospective = prospective
        self.filename = filename
        self.init_image_name = init_image_name
        self.nerf_output_image_name = f"output_{filename}"

class SocketMessage:
    def __init__(self, type: str, message: str):
        self.type = type
        self.message = message

    def to_pickle(self):
        return pickle.dumps(self)


if not_tokenized:
    model_path = "AdrianoC/RubberDuckProspectStableDiffusion_1_5"

    # Define the list of TrainElements
    train_elements = {
        "Top": TrainElement("Top", "top_camera.png", "init_top.png"),
        "Right Top": TrainElement("Right Top", "right_top.png", "init_right_top.png"),
        "Back Right Top": TrainElement("Back Right Top", "back_right_top.png", "init_back_right_top.png"),
        "Back Top": TrainElement("Back Top", "back_top.png", "init_back_top.png"),
        "Back Left Top": TrainElement("Back Left Top", "back_left_top.png", "init_back_left_top.png"),
        "Left Top": TrainElement("Left Top", "left_top.png", "init_left_top.png"),
        "Front Left Top": TrainElement("Front Left Top", "front_left_top.png", "init_front_left_top.png"),
        "Front Top": TrainElement("Front Top", "front_top.png", "init_front_top.png"),
        "Front Right Top": TrainElement("Front Right Top", "front_right_top.png", "init_front_right_top.png"),
        "Right": TrainElement("Right", "right.png", "init_right.png"),
        "Back Right": TrainElement("Back Right", "back_right.png", "init_back_right.png"),
        "Back": TrainElement("Back", "back.png", "init_back.png"),
        "Back Left": TrainElement("Back Left", "back_left.png", "init_back_left.png"),
        "Left": TrainElement("Left", "left.png", "init_left.png"),
        "Front Left": TrainElement("Front Left", "front_left.png", "init_front_left.png"),
        "Front": TrainElement("Front", "front.png", "init_front.png"),
        "Front Right": TrainElement("Front Right", "front_right.png", "init_front_right.png")
    }
else:
    model_path="AdrianoC/RubberDuckProspectStableDiffusion_1_5_tokens"
    train_elements = {
        "<top>": TrainElement("Top", "top_camera.png", "init_top.png"),
        "<left_top>": TrainElement("Right Top", "right_top.png", "init_right_top.png"),
        "<back_left_top>": TrainElement("Back Right Top", "back_right_top.png", "init_back_right_top.png"),
        "<back_top>": TrainElement("Back Top", "back_top.png", "init_back_top.png"),
        "<back_right_top>": TrainElement("Back Left Top", "back_left_top.png", "init_back_left_top.png"),
        "<right_top>": TrainElement("Left Top", "left_top.png", "init_left_top.png"),
        "<front_right_top>": TrainElement("Front Left Top", "front_left_top.png", "init_front_left_top.png"),
        "<front_top>": TrainElement("Front Top", "front_top.png", "init_front_top.png"),
        "<front_left_top>": TrainElement("Front Right Top", "front_right_top.png", "init_front_right_top.png"),
        "<left>": TrainElement("Right", "right.png", "init_right.png"),
        "<back_left>": TrainElement("Back Right", "back_right.png", "init_back_right.png"),
        "<back>": TrainElement("Back", "back.png", "init_back.png"),
        "<back_right>": TrainElement("Back Left", "back_left.png", "init_back_left.png"),
        "<right>": TrainElement("Left", "left.png", "init_left.png"),
        "<front_right>": TrainElement("Front Left", "front_left.png", "init_front_left.png"),
        "<front>": TrainElement("Front", "front.png", "init_front.png"),
        "<front_left>": TrainElement("Front Right", "front_right.png", "init_front_right.png")
    }


# %%
# Load the pipeline
def load_model(model_path):
    pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(model_path, torch_dtype=torch.float16)
    pipeline = pipeline.to("cuda")  # Use GPU if available
    pipeline.safety_checker = None
    return pipeline

# %%
start_image = Image.open("./start.png").convert("RGB")
start_image = start_image.resize((512, 512))  # Resize the image if necessary
# start_image.show()

# %%
string_time = time.strftime("%Y-%m-%d %H_%M_%S", current_time)
init_folder = "./init"
output_folder = "./output"
reconstruction_folder = "./outputs"
iter_folder = f"./iter/{string_time}"
diff_mod_image_folder = "./diff_mod_image"

if not os.path.exists(init_folder):
    os.makedirs(init_folder)

if not os.path.exists(iter_folder):
    os.makedirs(iter_folder)

if not os.path.exists(diff_mod_image_folder):
    os.makedirs(diff_mod_image_folder)

for train_element in train_elements.values():
    init_image = start_image.copy()
    init_image.save(f"./{train_element.nerf_output_image_name}")

# Convert to dictionary
# %%
 
pipeline: StableDiffusionImg2ImgPipeline = None
def generate_duck_images(model_path, strength=1):
    global diff_mod_image_folder
    global train_elements

    pipeline: StableDiffusionImg2ImgPipeline = load_model(model_path=model_path)

    for perspective, train_element in train_elements.items():
        init_image = Image.open(f"{init_folder}/{train_element.init_image_name}").convert("RGB")

        # path = f"{diff_mod_image_folder}/{train_element.filename}"
        prompt = f"yellow rubber duck seen from {perspective}"
        with torch.no_grad():
            output = pipeline(
                prompt=prompt,
                image=init_image,
                strength=strength,  # Controls how much the output differs from the original image
                guidance_scale=2.5,  # Controls how closely the model follows the prompt
                num_inference_steps=50,
            )
        output_image = output.images[0]
        #output_image.show()
        output_image.save(
            f"{diff_mod_image_folder}/{train_element.filename}"
        )
        """
        # save the init image as a 
        temp = init_image.copy()
        temp.save(path)
        """
    
    pipeline = None
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    torch.cuda.ipc_collect()

#%% 
command = [
    'ns-train',
    model_type,
    '--data', './', 
    '--max-num-iterations', str(steps),
    'nerfstudio-data',
    '--orientation-method', 'none',
    '--center_method', 'none'
]

#%% 
def kill_process():
    global process
    # Get the process PID
    process.terminate()
    process_killed_event.set()  # Signal to the main thread that the process is terminated

#%% 
def rename_new_file(iteration):
    print("rename...")
    global init_folder
    global iter_folder
    global diff_mod_image_folder
    global reconstruction_folder
    
    for perspective, train_element in train_elements.items():
        # Create the folder for the iteration
        temp_iter = f"{iter_folder}/{iteration}"
        if not os.path.exists(temp_iter):
            os.makedirs(temp_iter)

        # Save the old init file in the iteration folder
        init_path = f"{init_folder}/{train_element.init_image_name}"
        new_init_path = f"{iter_folder}/{iteration}/{train_element.init_image_name}"
        if os.path.exists(init_path):
            os.rename(init_path, new_init_path)
        
        # Save the old images generated by the diffusion model in the iteration folder
        model_image_path = f"{diff_mod_image_folder}/{train_element.filename}"
        new_model_image_path = f"{iter_folder}/{iteration}/{train_element.filename}"
        if os.path.exists(model_image_path):
            os.rename(model_image_path, new_model_image_path)

        # Save the new output images from the nerf as new init files
        output_path = f"./{train_element.nerf_output_image_name}"
        new_output_path = init_path
        if os.path.exists(output_path):
            os.rename(output_path, new_output_path)
    
    # Save the images generated by the nerf in the iteration folder
    if os.path.exists(reconstruction_folder):
        os.rename(reconstruction_folder, f"{iter_folder}/{iteration}/outputs")
    
    # Copy the file transforms_internal.json into the iteration folder as transforms.json
    if os.path.exists("./transforms_internal.json"):
        shutil.copyfile("./transforms_internal.json", f"{iter_folder}/{iteration}/transforms.json")
    else:
        print("File transforms_internal.json not found")

        
server_started = False

def read_stream(stream, stream_name):
    """
    Reads line by line from the stream (stdout/stderr) and prints it.
    """
    # Iterate over lines until an EOF signal ('') is received
    for line in iter(stream.readline, ''):
        if line:
            print(f"[{stream_name}] {line.strip()}")
    stream.close()

# %%
for iteration in range(max_iterations):

    rename_new_file(iteration)
    
    strength = np.exp(-0.7 * iteration/(max_iterations-1))
    generate_duck_images(model_path, strength=strength)

    nest_asyncio.apply()
    execution_count = 0
    lock = asyncio.Lock()  # Async Lock

    async def handle_messages(websocket):

        message: SocketMessage = pickle.loads(await websocket.recv())
        if(message.type == 'camera'):
            global execution_count
            async with lock:  # Ensure only one coroutine modifies the counter at a time
                execution_count += 1

            # Receive the filename
            filename = message.message
            print(f"Received file: {filename} {execution_count}")

            if(execution_count == 17):
                print("Killing process...")
                kill_process()
                print("Process killed")
                execution_count = 0 

        if(message.type == 'step'):
            print("Step: ", message.message)

    async def server_creation():
        async with serve(handle_messages, "localhost", 8765):
            await asyncio.get_running_loop().create_future()  # run forever

    def start_server():
        asyncio.run(server_creation())
    
    if not server_started:
        server_thread = threading.Thread(target=start_server)
        server_thread.start()
        
        server_started = True

    # ns-train instant-ngp --data .\ nerfstudio-data --orientation-method none --auto-scale-poses False

    print("Executing nerf-studio...")
    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        
        #stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, "STDOUT"))
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, "STDERR"))

        #stdout_thread.start()
        stderr_thread.start()

    except Exception as e:
        print(f"Error executing command: {e}")
        print(f"Error output: {e.stderr}")


    attempt = 0
    op = Options()
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=op)

    while attempt < max_attempts:
        print("Connecting to the browser...")
        try:
            # Use webdriver_manager to install and configure ChromeDriver

            # Open the site localhost:7007
            driver.get("http://localhost:7007")
            break

        except WebDriverException as e:
            time.sleep(10)
            print("Unable to connect to the site, retrying...")
            attempt += 1
    
    else:
        print("Error connecting to the browser, exiting the program...")
        driver.quit()
        break

    time.sleep(10)
    driver.quit()
    print("Connection successful!")
    print("Waiting for the process to terminate...")
    process_killed_event.wait()  # Wait for the process to be terminated by the server
    process_killed_event.clear()
    print("Process terminated, freeing memory...")

    print("Releasing memory...")
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    torch.cuda.ipc_collect()  # Helps release shared GPU memory between processes
    print("-------------------------------------")
    print(f"Iteration {iteration} completed, moving to the next one...")
    print("-------------------------------------")

rename_new_file(max_iterations + 1)
print("Iterations complete, exiting the program...")