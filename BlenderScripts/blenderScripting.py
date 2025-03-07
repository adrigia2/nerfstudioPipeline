from typing import Literal
import bpy
import math
import json
import os
import csv
import random

cameras = []

# ── UPDATED categorize_camera ──
# Here we subtract 90° from the computed alpha (and normalize) so that the original “Back” (alpha≈0)
# becomes “Right” (because 0 – 90 = –90, which falls into the “Right” sector in our adjusted mapping).
def categorize_camera(pos, center=(0, 0, 0)):
    cx, cy, cz = center
    x, y, z = pos
    rx = x - cx
    ry = y - cy
    rz = z - cz

    # Compute original angle (in degrees) with respect to positive Y.
    alpha = math.degrees(math.atan2(rx, ry))
    # Adjust horizontal angle by subtracting 90° so that "Back" becomes "Right".
    adj_alpha = alpha - 90
    # Normalize to [-180, 180]
    adj_alpha = ((adj_alpha + 180) % 360) - 180

    r_xy = math.sqrt(rx**2 + ry**2)
    theta = math.degrees(math.atan2(rz, r_xy))

    def horiz_sector(a):
        if -22.5 <= a < 22.5:
            return "Back"
        elif 22.5 <= a < 67.5:
            return "Back Left"
        elif 67.5 <= a < 112.5:
            return "Left"
        elif 112.5 <= a < 157.5:
            return "Front Left"
        elif a >= 157.5 or a < -157.5:
            return "Front"
        elif -157.5 <= a < -112.5:
            return "Front Right"
        elif -112.5 <= a < -67.5:
            return "Right"
        elif -67.5 <= a < -22.5:
            return "Back Right"
        return "Back"

    h = horiz_sector(adj_alpha)

    # Vertical categorization remains as before.
    if theta > 60:
        return "Top"
    elif theta > 30:
        return "Top " + h
    elif theta < -60:
        return "Bottom"
    elif theta < -30:
        return "Bottom " + h
    else:
        return h


def get_env_items(self, context):
    envs_base_path = getattr(context.scene, "envs_base_path", "")
    if not envs_base_path or not os.path.isdir(envs_base_path):
        return []

    max_depth = getattr(context.scene, "envs_max_depth", 1)
    items = []

    def recursive_search(directory, current_depth):
        if current_depth > max_depth:
            return
        for entry in os.listdir(directory):
            full_path = os.path.join(directory, entry)
            if os.path.isdir(full_path):
                recursive_search(full_path, current_depth + 1)
            elif entry.lower().endswith((".hdr", ".exr")):
                rel_path = os.path.relpath(full_path, envs_base_path)
                items.append((rel_path, rel_path, rel_path))

    recursive_search(envs_base_path, 1)
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
    tree = world.node_tree
    nodes = tree.nodes
    links = tree.links

    # Get or create the nodes we need
    bg_node = nodes.get("Background")
    if bg_node is None:
        bg_node = nodes.new("ShaderNodeBackground")
        bg_node.name = "Background"

    env_tex_node = nodes.get("Environment Texture")
    if env_tex_node is None:
        env_tex_node = nodes.new("ShaderNodeTexEnvironment")
        env_tex_node.name = "Environment Texture"
    else:
        # If an image is already loaded, clear its users and remove it
        if env_tex_node.image:
            old_image = env_tex_node.image
            env_tex_node.image = None  # Unlink it first
            # Clear all users to allow removal
            old_image.user_clear()
            bpy.data.images.remove(old_image, do_unlink=True)

    output_node = nodes.get("World Output")
    if output_node is None:
        output_node = nodes.new("ShaderNodeOutputWorld")
        output_node.name = "World Output"

    # Remove any existing links that might reference the old nodes
    for link in list(links):
        if link.to_node in {bg_node, output_node}:
            links.remove(link)

    # Load the new image. Using check_existing=False forces a fresh load.
    if os.path.exists(full_path):
        env_tex_node.image = bpy.data.images.load(full_path, check_existing=False)
    else:
        print(f"File not found: {full_path}")
        return

    # Re-establish the links
    links.new(env_tex_node.outputs["Color"], bg_node.inputs["Color"])
    links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

    bg_node.inputs["Strength"].default_value = 1.0


def add_properties():
    bpy.types.Scene.render_base_path = bpy.props.StringProperty(
        name="Render Base Path",
        description="Path to save rendered images and camera info",
        default="C:/",
        subtype="DIR_PATH",
    )

    bpy.types.Scene.envs_base_path = bpy.props.StringProperty(
        name="Environments Base Path",
        description="Path to the folder containing HDRIs",
        default="C:/",
        subtype="DIR_PATH",
    )

    bpy.types.Scene.envs_max_depth = bpy.props.IntProperty(
        name="Max Recursion Depth",
        description="Maximum folder depth for environment search",
        default=1,
        min=1,
    )

    bpy.types.Scene.env_path = bpy.props.EnumProperty(
        name="Environment",
        description="Environment to use",
        items=get_env_items,
        update=update_env_texture,
    )

    # New property replacing num_rings and cameras_per_ring.
    bpy.types.Scene.num_camera_per_category = bpy.props.IntProperty(
        name="Cameras per Category",
        description="Number of cameras to spawn for each category",
        default=1,
        min=1,
    )

    bpy.types.Scene.sphere_radius = bpy.props.FloatProperty(
        name="Sphere Radius",
        description="Radius of the sphere of cameras",
        default=10.0,
        min=0.1,
    )
    bpy.types.Scene.sphere_center = bpy.props.FloatVectorProperty(
        name="Sphere Center",
        description="Center of the sphere of cameras",
        default=(0.0, 0.0, 0.0),
        subtype="XYZ",
    )
    bpy.types.Scene.renderHalf = bpy.props.BoolProperty(
        name="Render Half", description="Render only half of the cameras", default=False
    )

    bpy.types.Scene.sensor_width = bpy.props.FloatProperty(
        name="Sensor Width",
        description="Width of the camera sensor",
        default=36.0,
        min=0.1,
    )

    bpy.types.Scene.noise_amount = bpy.props.FloatProperty(
        name="Noise Amount",
        description="Amount of noise added to camera angles",
        default=0.0,
        min=0.0,
    )


def create_camera(name: str, location: tuple, rotation: tuple, center: tuple,
                  sensor_fit: Literal["HORIZONTAL", "VERTICAL"] = "HORIZONTAL", flip=False, damped=False):
    bpy.ops.object.camera_add(location=location, rotation=rotation)
    camera = bpy.context.object
    camera.name = name
    camera.data.sensor_fit = sensor_fit

    bpy.ops.object.empty_add(location=center)
    empty = bpy.context.object
    empty.name = f"Target_{name}"
    camera.select_set(True)
    bpy.context.view_layer.objects.active = camera

    if damped:
        # Usa il constraint "DAMPED_TRACK" per le extreme top.
        constraint = camera.constraints.new(type="DAMPED_TRACK")
        constraint.target = empty
        # Impostiamo l'asse di tracking (es. TRACK_Z)
        constraint.track_axis = 'TRACK_NEGATIVE_Z'
    else:
        constraint = camera.constraints.new(type="TRACK_TO")
        constraint.target = empty
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.up_axis = "UP_Y"

    # Se flip è True, ruota il roll di 180°.
    if flip:
        camera.rotation_euler[2] += math.radians(180)
    return camera

def get_frame_data(camera, filepath):
    transform_matrix = [list(row) for row in camera.matrix_world]
    frame_data = {
        "file_path": filepath,
        "sharpness": 1.0,
        "transform_matrix": transform_matrix,
    }
    return frame_data


def render_camera(camera, filepath):
    bpy.context.scene.camera = camera
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    return get_frame_data(camera, filepath)


# ── UPDATED create_cameras_by_category ──
# Now we only spawn cameras in the upper half.
# The allowed horizontal intervals are defined (in terms of the original alpha)
# so that, after subtracting 90°, the mapping matches the new desired labels.
def create_cameras_by_category(num_camera_per_category, radius, center):
    clear_cameras()
    scene = bpy.context.scene
    noise_amount = scene.noise_amount
    camera_count = 1

    # Definizione delle categorie per l'emisfero superiore con i relativi range verticali (theta_code)
    # e orizzontali (alpha) definiti in termini dell'angolo originale.
    horizontal_categories = {
        "Back":         (-30, 30, [(67.5, 112.5)]),       # Centro = 90°
        "Back Right":   (-30, 30, [(112.5, 157.5)]),      # Centro = 135°
        "Right":        (-30, 30, [(157.5, 202.5)]),      # Centro = 180°
        "Front Right":  (-30, 30, [(202.5, 247.5)]),      # Centro = 225°
        "Front":        (-30, 30, [(247.5, 292.5)]),      # Centro = 270°
        "Front Left":   (-30, 30, [(-67.5, -22.5)]),      # Centro = -45°
        "Left":         (-30, 30, [(-22.5, 22.5)]),       # Centro = 0°
        "Back Left":    (-30, 30, [(22.5, 67.5)])         # Centro = 45°
    }
    moderate_top = { "Top " + k: (30, 60, v[2]) for k, v in horizontal_categories.items() }
    # Per l'estreme top, spawniamo solo telecamere nella fascia "Front" (range originale [(247.5, 292.5)]).
    extreme_top = { "Top": (80, 100, [(247.5, 292.5)]) }

    # Combina le categorie (solo emisfero superiore)
    all_categories = {}
    all_categories.update(horizontal_categories)
    all_categories.update(moderate_top)
    all_categories.update(extreme_top)

    for cat, (theta_min, theta_max, alpha_intervals) in all_categories.items():
        for i in range(num_camera_per_category):
            # Calcola il centro del range verticale e aggiunge rumore.
            theta_center = (theta_min + theta_max) / 2.0
            theta_code = theta_center + random.uniform(-noise_amount, noise_amount)
            # Per l'angolo orizzontale, sceglie un intervallo, ne prende il centro e aggiunge rumore.
            chosen_interval = random.choice(alpha_intervals)
            alpha_center = (chosen_interval[0] + chosen_interval[1]) / 2.0
            alpha_val = alpha_center + random.uniform(-noise_amount, noise_amount)
            
            # Se siamo nella categoria "Top" (estreme top) e theta_code > 90, attiva il flip.
            flip = False
            damped = False
            if cat == "Top":
                damped = True
                #if theta_code > 90:
                flip = True

            # Converte theta_code nell'angolo polare (theta_polar) usato per le coordinate sferiche.
            theta_polar = 90 - theta_code
            theta_polar_rad = math.radians(theta_polar)
            alpha_rad = math.radians(alpha_val)

            # Calcola la posizione sulla sfera (distanza costante).
            x = center[0] + radius * math.sin(theta_polar_rad) * math.cos(alpha_rad)
            y = center[1] + radius * math.sin(theta_polar_rad) * math.sin(alpha_rad)
            z = center[2] + radius * math.cos(theta_polar_rad)

            cam_name = f"Camera_{cat}_{camera_count}"
            create_camera(name=cam_name, location=(x, y, z), rotation=(0, 0, 0),
                          center=center, sensor_fit="HORIZONTAL", flip=flip, damped=damped)
            cameras.append(cam_name)
            camera_count += 1



def render_all_cameras(num_camera_per_category, radius, center, base_path):
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

    if cam.sensor_fit == "HORIZONTAL":
        sensor_height = sensor_width * (image_height / image_width)
    elif cam.sensor_fit == "VERTICAL":
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
        "aabb_scale": 16,
    }

    csv_filepath = os.path.join(base_path, "images.csv")

    for c in cameras:
        camera = bpy.data.objects[c]
        filepath = os.path.join("images", f"render_{c}.png")
        full_filepath = os.path.join(env_render_path, filepath)
        images_folder = os.path.join(env_render_path, "images")
        if not os.path.exists(images_folder):
            os.makedirs(images_folder)
        frame_data = render_camera(camera, full_filepath)
        frames.append(frame_data)
        with open(csv_filepath, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([full_filepath, env_name])
    camera_data["frames"] = frames
    with open(os.path.join(env_render_path, "transforms.json"), "w") as f:
        json.dump(camera_data, f, indent=4)


def clear_cameras():
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if obj.type == "CAMERA" or (obj.type == "EMPTY" and "Target" in obj.name):
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
        layout.prop(context.scene, "envs_max_depth")
        layout.separator()
        if not context.scene.envs_base_path:
            layout.label(text="No environment selected.")
        elif os.path.exists(context.scene.envs_base_path):
            layout.prop(context.scene, "env_path")
        layout.separator()
        layout.prop(context.scene, "num_camera_per_category")
        layout.prop(context.scene, "sphere_radius")
        layout.prop(context.scene, "sphere_center")
        layout.prop(context.scene, "renderHalf")
        layout.prop(context.scene, "noise_amount")
        layout.operator("camera.create_spherical_cameras", text="Create Cameras")
        layout.operator("camera.render_spherical_cameras", text="Render All Cameras")
        layout.operator("camera.clear_spherical_cameras", text="Clear Cameras")
        layout.operator("camera.print_camera_data", text="Print Camera Data")
        layout.operator("camera.render_all_environments", text="Render All Environments")


class CAMERA_OT_CreateSphericalCameras(bpy.types.Operator):
    bl_label = "Create Spherical Cameras"
    bl_idname = "camera.create_spherical_cameras"

    def execute(self, context):
        num_camera_per_category = context.scene.num_camera_per_category
        radius = context.scene.sphere_radius
        center = context.scene.sphere_center
        create_cameras_by_category(num_camera_per_category, radius, center)
        return {"FINISHED"}


class CAMERA_OT_RenderSphericalCameras(bpy.types.Operator):
    bl_label = "Render Spherical Cameras"
    bl_idname = "camera.render_spherical_cameras"

    def execute(self, context):
        num_camera_per_category = context.scene.num_camera_per_category
        radius = context.scene.sphere_radius
        center = context.scene.sphere_center
        base_path = context.scene.render_base_path
        render_all_cameras(num_camera_per_category, radius, center, base_path)
        return {"FINISHED"}


class CAMERA_OT_ClearSphericalCameras(bpy.types.Operator):
    bl_label = "Clear Spherical Cameras"
    bl_idname = "camera.clear_spherical_cameras"

    def execute(self, context):
        clear_cameras()
        return {"FINISHED"}


class CAMERA_PrintCameraData(bpy.types.Operator):
    bl_label = "Print Camera Data"
    bl_idname = "camera.print_camera_data"

    def execute(self, context):
        self.report({"INFO"}, "Camera data:")
        for cam in context.scene.objects:
            if cam.type == "CAMERA":
                self.report(
                    {"INFO"},
                    "Camera: " + cam.name +
                    "\nLens: " + str(cam.data.lens) +
                    "\nSensor width: " + str(cam.data.sensor_width) +
                    "\nSensor height: " + str(cam.data.sensor_height)
                )
        return {"FINISHED"}

def cleanup_unused_images():
    for img in list(bpy.data.images):
        if img.users == 0:
            bpy.data.images.remove(img, do_unlink=True)


class CAMERA_OT_RenderAllEnvironments(bpy.types.Operator):
    bl_label = "Render All Environments"
    bl_idname = "camera.render_all_environments"

    def execute(self, context):
        scene = context.scene
        base_path = scene.render_base_path
        envs_base_path = scene.envs_base_path
        num_camera_per_category = scene.num_camera_per_category
        radius = scene.sphere_radius
        center = scene.sphere_center

        if not envs_base_path or not os.path.isdir(envs_base_path):
            self.report({"WARNING"}, "Invalid environments base path.")
            return {"CANCELLED"}

        env_files = [f[0] for f in get_env_items(self, context)]
        if not env_files:
            self.report({"WARNING"}, "No environments found.")
            return {"CANCELLED"}

        for env_file in env_files:
            clear_cameras()
            scene.env_path = env_file
            create_cameras_by_category(num_camera_per_category, radius, center)
            render_all_cameras(num_camera_per_category, radius, center, base_path)
            # Clean up any unused images to free VRAM
            cleanup_unused_images()
        self.report({"INFO"}, "Rendering of all environments completed.")
        return {"FINISHED"}


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
    del bpy.types.Scene.num_camera_per_category
    del bpy.types.Scene.sphere_radius
    del bpy.types.Scene.sphere_center
    del bpy.types.Scene.renderHalf
    del bpy.types.Scene.sensor_width
    del bpy.types.Scene.noise_amount


if __name__ == "__main__":
    register()
