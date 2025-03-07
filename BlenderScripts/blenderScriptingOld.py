from typing import Literal
import bpy
import math
import json
import os
import csv
import random

cameras = []

def categorize_camera(pos, center=(0,0,0)):
    cx, cy, cz = center
    x, y, z = pos
    rx = x - cx
    ry = y - cy
    rz = z - cz

    alpha = math.degrees(math.atan2(rx, ry))
    r_xy = math.sqrt(rx**2 + ry**2)
    theta = math.degrees(math.atan2(rz, r_xy))

    def horiz_sector(a):
        if -22.5 <= a < 22.5:
            return "Back"
        elif 22.5 <= a < 67.5:
            return "Back Right"
        elif 67.5 <= a < 112.5:
            return "Right"
        elif 112.5 <= a < 157.5:
            return "Front Right"
        elif a >= 157.5 or a < -157.5:
            return "Front"
        elif -157.5 <= a < -112.5:
            return "Front Left"
        elif -112.5 <= a < -67.5:
            return "Left"
        elif -67.5 <= a < -22.5:
            return "Back Left"
        return "Back"
    
    def vert_sector(t):
        if t > 45:
            return "Top"
        elif t < -45:
            return "Bottom"
        else:
            return ""

    h = horiz_sector(alpha)
    v = vert_sector(theta)

    if v:
        return f"{h} {v}".strip()
    else:
        return h

def get_env_items(self, context):
    envs_base_path = getattr(context.scene, "envs_base_path", "")
    if not envs_base_path or not os.path.isdir(envs_base_path):
        return []
    files = os.listdir(envs_base_path)
    items = [(f, f, f) for f in files if f.lower().endswith(('.hdr', '.exr'))]
    return items

def update_env_texture(self, context):
    env_path = context.scene.env_path
    envs_base_path = context.scene.envs_base_path

    if not env_path:
        return

    full_path = os.path.join(envs_base_path, env_path)

    world = context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    bg_node = nodes.get("Background")
    if bg_node is None:
        bg_node = nodes.new("ShaderNodeBackground")
        bg_node.name = "Background"

    env_tex_node = nodes.get("Environment Texture")
    if env_tex_node is None:
        env_tex_node = nodes.new("ShaderNodeTexEnvironment")
        env_tex_node.name = "Environment Texture"

    output_node = nodes.get("World Output")
    if output_node is None:
        output_node = nodes.new("ShaderNodeOutputWorld")
        output_node.name = "World Output"

    if os.path.exists(full_path):
        env_tex_node.image = bpy.data.images.load(full_path, check_existing=True)
    else:
        print(f"File not found: {full_path}")
        return

    for link in links:
        if link.to_node == bg_node and link.to_socket.name == "Color":
            links.remove(link)
    for link in links:
        if link.to_node == output_node and link.to_socket.name == "Surface":
            links.remove(link)

    links.new(env_tex_node.outputs["Color"], bg_node.inputs["Color"])
    links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

    bg_node.inputs["Strength"].default_value = 1.0

def add_properties():
    bpy.types.Scene.render_base_path = bpy.props.StringProperty(
        name="Render Base Path",
        description="Path to save rendered images and camera info",
        default="C:/",
        subtype='DIR_PATH'
    )

    bpy.types.Scene.envs_base_path = bpy.props.StringProperty(
        name="Environments Base Path",
        description="Path to the folder containing HDRIs",
        default="C:/",
        subtype='DIR_PATH'
    )

    bpy.types.Scene.env_path = bpy.props.EnumProperty(
        name="Environment",
        description="Environment to use",
        items=get_env_items,
        update=update_env_texture
    )

    bpy.types.Scene.num_rings = bpy.props.IntProperty(
        name="Number of Rings",
        description="Number of rings in the top hemisphere",
        default=3,
        min=1
    )
    bpy.types.Scene.cameras_per_ring = bpy.props.IntProperty(
        name="Cameras per Ring",
        description="Number of cameras in each ring",
        default=8,
        min=1
    )
    bpy.types.Scene.sphere_radius = bpy.props.FloatProperty(
        name="Sphere Radius",
        description="Radius of the sphere of cameras",
        default=10.0,
        min=0.1
    )
    bpy.types.Scene.sphere_center = bpy.props.FloatVectorProperty(
        name="Sphere Center",
        description="Center of the sphere of cameras",
        default=(0.0, 0.0, 0.0),
        subtype='XYZ'
    )
    bpy.types.Scene.renderHalf = bpy.props.BoolProperty(
        name="Render Half",
        description="Render only half of the cameras",
        default=False
    )

    bpy.types.Scene.sensor_width = bpy.props.FloatProperty(
        name="Sensor Width",
        description="Width of the camera sensor",
        default=36.0,
        min=0.1
    )

    bpy.types.Scene.noise_amount = bpy.props.FloatProperty(
        name="Noise Amount",
        description="Amount of noise added to camera positions",
        default=0.0,
        min=0.0
    )

def create_camera(name: str, location: tuple, rotation: tuple, center: tuple, sensor_fit: Literal['HORIZONTAL', 'VERTICAL'] = 'HORIZONTAL'):
    bpy.ops.object.camera_add(location=location, rotation=rotation)
    camera = bpy.context.object
    camera.name = name
    camera.data.sensor_fit = sensor_fit

    bpy.ops.object.empty_add(location=center)
    empty = bpy.context.object
    empty.name = f"Target_{name}"
    camera.select_set(True)
    bpy.context.view_layer.objects.active = camera
    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = empty
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'
    return camera

def get_frame_data(camera, filepath):
    transform_matrix = [list(row) for row in camera.matrix_world]
    frame_data = {
        "file_path": filepath,
        "sharpness": 1.0,
        "transform_matrix": transform_matrix
    }
    return frame_data

def render_camera(camera, filepath):
    bpy.context.scene.camera = camera
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    return get_frame_data(camera, filepath)

def create_top_hemisphere_with_base_cameras(num_cameras_per_ring, radius, num_rings, half, center):
    clear_cameras()

    scene = bpy.context.scene
    noise_amount = scene.noise_amount

    camera_count = 1

    x = center[0]
    y = center[1]
    z = center[2] + radius

    x += random.uniform(-noise_amount, noise_amount)
    y += random.uniform(-noise_amount, noise_amount)
    z += random.uniform(-noise_amount, noise_amount)

    dx = x - center[0]
    dy = y - center[1]
    dz = z - center[2]
    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
    scale_factor = radius / dist
    x = center[0] + dx*scale_factor
    y = center[1] + dy*scale_factor
    z = center[2] + dz*scale_factor

    top_camera_name= f"Top_Camera_{camera_count}"
    create_camera(name=top_camera_name, location=(x, y, z), rotation=(math.pi, 0, 0), sensor_fit='HORIZONTAL', center=center)
    cameras.append(top_camera_name)

    camera_count += 1

    for j in range(1, num_rings + 2):
        theta = j * (math.pi / 2) / (num_rings + 1)
        angle_step = 2 * math.pi / num_cameras_per_ring

        for i in range(num_cameras_per_ring):
            phi = i * angle_step
            x = center[0] + radius * math.sin(theta) * math.cos(phi)
            y = center[1] + radius * math.sin(theta) * math.sin(phi)
            z = center[2] + radius * math.cos(theta)

            x += random.uniform(-noise_amount, noise_amount)
            y += random.uniform(-noise_amount, noise_amount)
            z += random.uniform(-noise_amount, noise_amount)

            dx = x - center[0]
            dy = y - center[1]
            dz = z - center[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            scale_factor = radius / dist
            x = center[0] + dx*scale_factor
            y = center[1] + dy*scale_factor
            z = center[2] + dz*scale_factor

            categoria = categorize_camera((x, y, z), center)
            camera_name = f"Camera_{categoria}_{camera_count}"
            create_camera(name=camera_name, location=(x, y, z), rotation=(math.pi / 2, 0, -phi), sensor_fit='HORIZONTAL', center=center)
            cameras.append(camera_name)
            camera_count += 1

def render_all_cameras(num_cameras_per_ring, num_rings, radius, center, base_path):
    scene = bpy.context.scene
    env_path = scene.env_path
    env_name = os.path.splitext(os.path.basename(env_path))[0]

    env_render_path = os.path.join(base_path, env_name)
    if not os.path.exists(env_render_path):
        os.makedirs(env_render_path)

    frames = []

    cam = bpy.data.cameras[0]
    focal_length = cam.lens

    sensor_width = cam.sensor_width
    sensor_height = cam.sensor_height

    render = scene.render

    image_width = render.resolution_x
    image_height = render.resolution_y

    if cam.sensor_fit == 'HORIZONTAL':
        sensor_height = sensor_width * (image_height / image_width)
    elif cam.sensor_fit == 'VERTICAL':
        sensor_width = sensor_height * (image_width / image_height)

    camera_angle_x = 2 * math.atan((sensor_width / 2) / focal_length)
    camera_angle_y = 2 * math.atan((sensor_height / 2) / focal_length)

    fl_x = (focal_length / sensor_width) * image_width
    fl_y = (focal_length / sensor_height) * image_height

    camera_data = {
        "camera_angle_x": camera_angle_x,
        "camera_angle_y": camera_angle_y,
        "fl_x": fl_x,
        "fl_y": fl_y,
        "cx": image_width / 2,
        "cy": image_height / 2,
        "w": image_width,
        "h": image_height,
        "scale": 2 / radius,
        "aabb_scale": 16
    }

    csv_filepath = os.path.join(base_path, "images.csv")
    file_exists = os.path.exists(csv_filepath)

    for c in cameras:
        camera = bpy.data.objects[c]
        filepath = os.path.join("images", f"render_{c}.png")
        full_filepath = os.path.join(env_render_path, filepath)

        images_folder = os.path.join(env_render_path, "images")
        if not os.path.exists(images_folder):
            os.makedirs(images_folder)

        frame_data = render_camera(camera, full_filepath)
        frames.append(frame_data)

        with open(csv_filepath, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([full_filepath, env_name])

    camera_data["frames"] = frames
    with open(os.path.join(env_render_path, "transforms.json"), "w") as f:
        json.dump(camera_data, f, indent=4)

def clear_cameras():
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'CAMERA' or (obj.type == 'EMPTY' and 'Target' in obj.name):
            obj.select_set(True)
    bpy.ops.object.delete()
    cameras.clear()

class CAMERA_PT_SphericalSetupPanel(bpy.types.Panel):
    bl_label = "Spherical Camera Setup"
    bl_idname = "CAMERA_PT_spherical_setup_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Spherical Camera"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "render_base_path")
        layout.prop(context.scene, "envs_base_path")

        layout.separator()
        if context.scene.envs_base_path == "" or context.scene.envs_base_path is None:
            layout.label(text="No environment selected.")
        if os.path.exists(context.scene.envs_base_path):
            layout.prop(context.scene, "env_path")
        layout.separator()

        layout.prop(context.scene, "num_rings")
        layout.prop(context.scene, "cameras_per_ring")
        layout.prop(context.scene, "sphere_radius")
        layout.prop(context.scene, "sphere_center")
        layout.prop(context.scene, "renderHalf")
        layout.prop(context.scene, "noise_amount")

        layout.operator("camera.create_spherical_cameras", text="Create Cameras")
        layout.operator("camera.render_spherical_cameras", text="Render All Cameras")
        layout.operator("camera.clear_spherical_cameras", text="Clear Cameras")
        layout.operator("camera.print_camera_data", text="Print Camera Data")
        
        # Nuovo pulsante per renderizzare tutti gli environment
        layout.operator("camera.render_all_environments", text="Render All Environments")


class CAMERA_OT_CreateSphericalCameras(bpy.types.Operator):
    bl_label = "Create Spherical Cameras"
    bl_idname = "camera.create_spherical_cameras"
    
    def execute(self, context):
        num_cameras_per_ring = context.scene.cameras_per_ring
        radius = context.scene.sphere_radius
        num_rings = context.scene.num_rings
        half = context.scene.renderHalf
        center = context.scene.sphere_center
        create_top_hemisphere_with_base_cameras(num_cameras_per_ring, radius, num_rings, half, center)
        return {'FINISHED'}

class CAMERA_OT_RenderSphericalCameras(bpy.types.Operator):
    bl_label = "Render Spherical Cameras"
    bl_idname = "camera.render_spherical_cameras"
    
    def execute(self, context):
        num_cameras_per_ring = context.scene.cameras_per_ring
        num_rings = context.scene.num_rings
        radius = context.scene.sphere_radius
        center = context.scene.sphere_center
        base_path = context.scene.render_base_path
        render_all_cameras(num_cameras_per_ring, num_rings, radius, center, base_path)
        return {'FINISHED'}

class CAMERA_OT_ClearSphericalCameras(bpy.types.Operator):
    bl_label = "Clear Spherical Cameras"
    bl_idname = "camera.clear_spherical_cameras"
    
    def execute(self, context):
        clear_cameras()
        return {'FINISHED'}

class CAMERA_PrintCameraData(bpy.types.Operator):
    bl_label = "Print Camera Data"
    bl_idname = "camera.print_camera_data"
    
    def execute(self, context):
        self.report({"INFO"},"Camera data:")
        for cam in context.scene.objects:
            if cam.type == 'CAMERA':
                self.report({"INFO"},"Camera:" + str(cam.name)+ "\n" +
                "lens"+ str(cam.data.lens) + "\n" +
                "sensor width: "+ str(cam.data.sensor_width) + "\n" +
                "sensor height: "+ str(cam.data.sensor_height))
        return {'FINISHED'}

class CAMERA_OT_RenderAllEnvironments(bpy.types.Operator):
    bl_label = "Render All Environments"
    bl_idname = "camera.render_all_environments"

    def execute(self, context):
        scene = context.scene
        base_path = scene.render_base_path
        envs_base_path = scene.envs_base_path
        num_cameras_per_ring = scene.cameras_per_ring
        num_rings = scene.num_rings
        radius = scene.sphere_radius
        center = scene.sphere_center

        if not envs_base_path or not os.path.isdir(envs_base_path):
            self.report({"WARNING"}, "Invalid environments base path.")
            return {'CANCELLED'}

        # Ottieni tutti i file HDR/EXR
        files = os.listdir(envs_base_path)
        env_files = [f for f in files if f.lower().endswith(('.hdr', '.exr'))]

        if not env_files:
            self.report({"WARNING"}, "No environments found.")
            return {'CANCELLED'}

        for env_file in env_files:
            # Cancella eventuali telecamere precedenti
            clear_cameras()

            # Imposta l'env_path sulla scena e aggiorna l'HDRI
            scene.env_path = env_file

            # Ricrea le telecamere per questo environment
            create_top_hemisphere_with_base_cameras(num_cameras_per_ring, radius, num_rings, scene.renderHalf, center)

            # Renderizza le telecamere con l'environment corrente
            render_all_cameras(num_cameras_per_ring, num_rings, radius, center, base_path)

            # Dopo il rendering non è obbligatorio pulire qui,
            # verrà comunque fatto all'inizio del loop alla prossima iterazione.
            # Se preferisci farlo subito:
            # clear_cameras()

        self.report({"INFO"}, "Rendering of all environments completed.")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(CAMERA_PT_SphericalSetupPanel)
    bpy.utils.register_class(CAMERA_OT_CreateSphericalCameras)
    bpy.utils.register_class(CAMERA_OT_RenderSphericalCameras)
    bpy.utils.register_class(CAMERA_OT_ClearSphericalCameras)
    bpy.utils.register_class(CAMERA_PrintCameraData)
    bpy.utils.register_class(CAMERA_OT_RenderAllEnvironments)
    add_properties()

def unregister():
    bpy.utils.unregister_class(CAMERA_PT_SphericalSetupPanel)
    bpy.utils.unregister_class(CAMERA_OT_CreateSphericalCameras)
    bpy.utils.unregister_class(CAMERA_OT_RenderSphericalCameras)
    bpy.utils.unregister_class(CAMERA_OT_ClearSphericalCameras)
    bpy.utils.unregister_class(CAMERA_PrintCameraData)
    bpy.utils.unregister_class(CAMERA_OT_RenderAllEnvironments)

    del bpy.types.Scene.render_base_path
    del bpy.types.Scene.envs_base_path
    del bpy.types.Scene.env_path
    del bpy.types.Scene.num_rings
    del bpy.types.Scene.cameras_per_ring
    del bpy.types.Scene.sphere_radius
    del bpy.types.Scene.sphere_center
    del bpy.types.Scene.renderHalf
    del bpy.types.Scene.sensor_width
    del bpy.types.Scene.noise_amount

if __name__ == "__main__":
    register()
