import nodes
from transformers import ViTModel, CLIPModel, CLIPProcessor
from torchmetrics.multimodal.clip_score import CLIPScore
from PIL import Image
from torchvision import transforms
import torch
import numpy as np
from torch.nn import functional as F
import comfy

class Dino_Score:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {"Source_Image": ("IMAGE", ),
                        "Target_Image": ("IMAGE", ),
            },
        }
    
    RETURN_TYPES = ("STRING", )
    
    RETURN_NAMES = ("Dino_Score", )

    FUNCTION = "execute"

    CATEGORY = "Image_Evaluation"

    def prepare_model(self, Device):
        dino_model = ViTModel.from_pretrained('facebook/dino-vits16').to(Device)
        return dino_model  
     
    def tensor_to_image(self, tensor):
        tensor = tensor.squeeze(0).cpu().numpy()
        image = Image.fromarray(np.uint8(tensor * 255))
        return image
    
    def get_dino_score(self, source_image, target_image, dino_model, Device):
        dino_transform = transforms.Compose([
            transforms.Resize(256, interpolation=3),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        source_image = dino_transform(source_image)
        target_image = dino_transform(target_image)
        source_image = source_image.to(Device)
        target_image = target_image.to(Device)
        with torch.no_grad():
            source_outputs = dino_model(source_image.unsqueeze(0))
            target_outputs = dino_model(target_image.unsqueeze(0))
        dino_similarity = F.cosine_similarity(source_outputs.last_hidden_state[0, 0], target_outputs.last_hidden_state[0, 0], dim=0).item()
        return dino_similarity

    def execute(self, Source_Image, Target_Image):
        dino_score = 0
        Device = comfy.model_management.get_torch_device()
        dino_model = self.prepare_model(Device)        
        Source_Image = Source_Image.to(Device)
        Target_Image = Target_Image.to(Device)
        Source_Image = self.tensor_to_image(Source_Image)
        Target_Image = self.tensor_to_image(Target_Image)
        dino_score = self.get_dino_score(source_image=Source_Image, target_image=Target_Image, dino_model=dino_model, Device=Device)
        return (str(dino_score), )




class Clip_Score:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {"Source_Image": ("IMAGE", ),
                        "Clip_Model": (["openai/clip-vit-large-patch14", "openai/clip-vit-base-patch16", "openai/clip-vit-base-patch32"], ),
            },
            "optional": {"Target_Image": ("IMAGE", ),
                        "Target_Prompt": ("STRING", ),
            },
        }

    RETURN_TYPES = ("STRING","STRING")

    RETURN_NAMES = ("Clip_Text_Score","Clip_Image_Score")

    FUNCTION = "execute"

    CATEGORY = "Image_Evaluation"

    def prepare_model(self, Clip_Model, Device):
        clip_model = CLIPModel.from_pretrained(Clip_Model).to(Device)
        clip_metric = CLIPScore(model_name_or_path=Clip_Model).to(Device)
        clip_processor = CLIPProcessor.from_pretrained(Clip_Model)
        return clip_model, clip_metric, clip_processor
    
    def get_clip_features(self, image, clip_model, clip_processor, Device):
        image = clip_processor(images=image, return_tensors="pt")
        image = image.to(Device)
        with torch.no_grad():
            outputs = clip_model.get_image_features(**image)
        return outputs[0]
    
    def tensor_to_image(self, tensor):
        tensor = tensor.squeeze(0).cpu().numpy()
        image = Image.fromarray(np.uint8(tensor * 255))
        return image
    
    def get_clip_image_score(self, image, target_image, clip_model, clip_processor, Device):
        image_feature_clip = self.get_clip_features(image, clip_model, clip_processor, Device)
        ref_feature_clip = self.get_clip_features(target_image, clip_model, clip_processor, Device)
        similarity_clip = F.cosine_similarity(ref_feature_clip, image_feature_clip, dim=0).item()
        return str(similarity_clip)
    
    def get_clip_text_score(self, image, ref_text, clip_metric, Device):
        clip_transform = transforms.Compose([
        transforms.Resize(256, interpolation=Image.BICUBIC),
        transforms.CenterCrop(224),
        transforms.ToTensor()
        ])
        image = clip_transform(image).unsqueeze(0) * 255
        image = image.to(Device)
        score = clip_metric(image, ref_text).item()
        return str(score)
    
    def execute(self, Source_Image, Clip_Model, Target_Image=None, Target_Prompt=None):
        clip_text_score = 0
        clip_image_score = 0
        Device = comfy.model_management.get_torch_device()
        Source_Image = Source_Image.to(Device)
        if Target_Image is not None:
            Target_Image = Target_Image.to(Device)
        Source_Image = self.tensor_to_image(Source_Image)
        clip_model, clip_metric, clip_processor = self.prepare_model(Clip_Model, Device)
        if Target_Image is not None and Target_Prompt is not None:
            Target_Image = self.tensor_to_image(Target_Image)
            clip_text_score = self.get_clip_text_score(image=Source_Image, ref_text=Target_Prompt, clip_metric=clip_metric, Device=Device)
            clip_image_score = self.get_clip_image_score(image=Source_Image, target_image=Target_Image, clip_model=clip_model, clip_processor=clip_processor, Device=Device)
            return (clip_text_score, clip_image_score)
        elif len(Target_Prompt) == 0:
            clip_image_score = self.get_clip_image_score(image=Source_Image, target_image=Target_Image, clip_model=clip_model, clip_processor=clip_processor, Device=Device)
            return ("None", clip_image_score)
        elif Target_Image is None:
            clip_text_score = self.get_clip_text_score(image=Source_Image, ref_text=Target_Prompt, clip_metric=clip_metric, Device=Device)
            return (clip_text_score, "None")
        else:
            return ("None", "None")

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "Clip_Score-🔬": Clip_Score,
    "Dino_Score-🔬": Dino_Score,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "Clip_Score-🔬": "Clip_Score",
    "Dino_Score-🔬": "Dino_Score",
}

