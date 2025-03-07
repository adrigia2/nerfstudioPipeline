# 3D Model Generator Setup Notebook

This notebook guides you through setting up your environment for Nerfstudio, including installing Anaconda, CUDA, PyTorch, and the necessary projects.

> **Note:** Execute these commands inside a folder

> **Important:** This installation process follows the original Nerfstudio installation with one key difference—step **7** installs my fork of Nerfstudio. (Step **8** is used only for Gaussian Splatting.)

---

## 1. Install Anaconda

Download Anaconda from [here](https://www.anaconda.com/download).

> **Note:** Follow the installation instructions on the website for your operating system.

---

## 2. Install CUDA

Download the latest version of CUDA from [here](https://developer.nvidia.com/cuda-downloads).

> **Tip:** Make sure your GPU is supported and check the release notes for any special installation instructions.

---

## 3. Create and Activate a New Anaconda Environment

Use a Code cell to create and activate your environment:

```bash
conda create -n nerfstudiotest python=3.11.10
conda activate nerfstudiotest
```
---

## 4. Install PyTorch
Install PyTorch with CUDA support using the following command:

```bash
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```
---

## 5. Install CUDA Toolkit
Install the CUDA toolkit through Conda:
```bash
conda install -c "nvidia/label/cuda-12.4.1" cuda-toolkit
```
---

## 6. Install tinycuda
Install tinycuda using Git:
```bash
pip install git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
```
---

## !!!!! 7. Install My Nerfstudio Fork Implementation !!!!!
Clone the repository and install your fork:
```bash
git clone -b dev https://github.com/adrigia2/nerfstudioCameraScreen.git
cd nerfstudioCameraScreen
pip install --upgrade pip setuptools
pip install -e .
```
---

## 8. Install Gaussian Splatting
Install Gaussian Splatting:

```bash
pip install git+https://github.com/nerfstudio-project/gsplat.git
```
for some issues check [this](https://github.com/nerfstudio-project/nerfstudio/issues/2727) discussion


# Huggingface Models
To use Hugging Face models, you first need to install the necessary dependencies.
```bash
pip install diffusers transformers accelerate scipy safetensors datasets
```
---
## 1. Models Test
To test the model run see the folder ```test_diffusion_model```

---

## 2. Dataset Script
To see the datasets related script see ```3d_model_generator.ipynb```
