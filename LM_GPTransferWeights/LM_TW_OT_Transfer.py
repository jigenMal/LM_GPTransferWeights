# LM GPTransferWeights: Transfer weights from one mesh to grease pencil strokes
# Copyright (C) 2025 Luca Malisan

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# Transfer operator for transferring weights from a mesh to grease pencil strokes

import bpy
import mathutils
import bmesh

class LM_TW_OT_Transfer(bpy.types.Operator):
    """Transfer weights from a mesh to grease pencil strokes"""
    bl_idname = "lm_tw.transfer"
    bl_label = "Transfer Weights"
    bl_description = "Transfer weights from a mesh to grease pencil strokes"
    bl_options = {'REGISTER', 'UNDO'}

    # this function is needed in Blender 4.3/4.4 that have a bug preventing writing vertex groups in Grease Pencil object.
    # it converts a temporary attribute to data in the vertex group using geometry nodes
    # weights must be stored in a temporary attribute with a different name
    def copy_attribute_using_geometry_nodes(self, bl_obj, from_attr_name, to_attr_name, to_the_top = False):
        bl_node_group = bpy.data.node_groups.new("__copy_attribute", "GeometryNodeTree")
        bl_node_group.is_modifier = True

        bl_node_group.interface.new_socket("Geometry", in_out = "INPUT", socket_type = "NodeSocketGeometry")
        bl_node_group.interface.new_socket("Geometry", in_out = "OUTPUT", socket_type = "NodeSocketGeometry")

        bl_input_node = bl_node_group.nodes.new("NodeGroupInput")
        bl_output_node = bl_node_group.nodes.new("NodeGroupOutput")

        bl_read_attr_node = bl_node_group.nodes.new("GeometryNodeInputNamedAttribute")
        bl_read_attr_node.inputs[0].default_value = from_attr_name

        bl_write_attr_node = bl_node_group.nodes.new("GeometryNodeStoreNamedAttribute")
        bl_write_attr_node.inputs[2].default_value = to_attr_name

        # Group Input.Geometry -> Store Named Attribute.Geometry
        bl_node_group.links.new(bl_input_node.outputs[0], bl_write_attr_node.inputs[0])

        # Named Attribute.Attribute -> Store Named Attribute.Value
        bl_node_group.links.new(bl_read_attr_node.outputs[0], bl_write_attr_node.inputs[3])

        # Store Named Attribute.Geometry -> Group Output.Geometry
        bl_node_group.links.new(bl_write_attr_node.outputs[0], bl_output_node.inputs[0])

        bpy.context.view_layer.objects.active = bl_obj
        bl_modifier_name = "LM TW Copy attribute"
        # we must apply the modifier to all frames of the grease pencil object
        # so we create a modifier for each frame in each layer
        # for layer in bl_obj.data.layers:
        #     for frame in layer.frames:
        #         bpy.context.scene.frame_current = frame.frame_number

        ###################
        # # Create a new modifier to apply the geometry nodes                
        bl_modifier = bl_obj.modifiers.new(bl_modifier_name, "NODES")
        if to_the_top:
            # Move the modifier to the top of the stack
            while bl_obj.modifiers[0].name != bl_modifier_name:
                bpy.ops.object.modifier_move_up(modifier=bl_modifier_name)
        
        bl_modifier.node_group = bl_node_group
        bpy.ops.object.modifier_apply(modifier = bl_modifier_name,all_keyframes=True)
        ######################

        bpy.data.node_groups.remove(bl_node_group)

    # main function
    def execute(self, context):

        # Check if we are in Blender 4.3 or later
        def is_GP3():
            """Check if the current Blender version is 4.3 or later"""
            return hasattr(context.scene.lm_tw_target_gp.data.layers[0].frames[0], 'drawing')
        
        # find the nearest vertex
        def find_nearest_vertex(point_co, source_vertices):            
            closest_dist = context.scene.lm_tw_distance
            if closest_dist == 0:
                closest_dist = float('inf')

            closest_vert_index = None
            # Check distance to each vertex in source mesh. If distance is greater than threshold, skip                   
            for index, pos in source_vertices:
                dist = (point_co - pos).length
                if dist < closest_dist:
                    closest_dist = dist
                    closest_vert_index = index

            return closest_vert_index
        
        # find the nearest face
        def find_nearest_face(point_co, source_obj):
            closest_dist = context.scene.lm_tw_distance
            if closest_dist == 0:
                closest_dist = float('inf')
            
            bm_b = bmesh.new()
            bm_b.from_mesh(source_obj.data)

            for face in bm_b.faces:
                face_center = sum((v.co for v in face.verts), mathutils.Vector()) / len(face.verts)
                if context.scene.lm_tw_mode == 'CURRENT':
                    # For CURRENT mode, we need to apply the transformation matrix of the object
                    face_center = source_obj.matrix_world @ face_center
                dist = (face_center - point_co).length
                if dist < closest_dist:
                    closest_dist = dist
                    nearest_face = face
            
            return [v.index for v in nearest_face.verts]

        

        # Start the operator
        try:
            
            source = context.scene.lm_tw_source_mesh
            target = context.scene.lm_tw_target_gp

            if source is None:
                raise ValueError("No source mesh selected")
                
            if target is None:
                raise ValueError("No target object selected")

            if source.type != 'MESH':
                raise ValueError("Source must be a mesh object")
                
            if target.type != 'GPENCIL' and target.type != 'GREASEPENCIL':
                raise ValueError("Target must be a grease pencil object")
            
            print("Transferring weights from", source.name, "to", target.name)         

            # Get all vertex groups from source mesh
            source_vgroups = source.vertex_groups

            # temporary prefix for attributes in Blender 4.3 and later
            temp_attr_prefix = "lm_tw_temp_"

            # Ensure target has matching vertex groups
            for vgroup in source_vgroups:
                # print("Checking vertex group:", vgroup.name)
                # If target does not have this vertex group, create it
                # note that in Blender 4.3 and later, we will also have to create attributes, we'll do it in a later loop                

                if vgroup.name not in target.vertex_groups:
                    target.vertex_groups.new(name=vgroup.name)

                # "Initialize" the vertex group by setting a weight for a random point.
                # If we don't do this, the geometry node setup will write to a new attribute rather than to the vertex group.
                # And we need to do this for every frame in the grease pencil object
                # This is needed in Blender 4.3 and later, but we do it for all versions to make sure VGroups are initialized correctly
                target.vertex_groups.active = target.vertex_groups.get(vgroup.name)
                context.view_layer.objects.active = target
                bpy.ops.object.mode_set(mode = "EDIT")
                for layer in target.data.layers:
                    for frame in layer.frames:
                        bpy.context.scene.frame_current = frame.frame_number
                        try:
                            frame.drawing.strokes[0].points[0].select = True
                        except:
                            # If there are no strokes, we can't assign a weight
                            continue
                        bpy.ops.object.vertex_group_assign()
                        bpy.ops.object.vertex_group_remove_from()
                bpy.ops.object.mode_set(mode = "OBJECT")
                  
            
            # Loop through all grease pencil layers
            for layer in target.data.layers:
                # Loop through all frames in this layer

                # Skip locked layers
                if layer.lock:
                    continue
                
                for frame in layer.frames:
                    print("Processing frame:", frame.frame_number)

                    # if we evaluate the mesh in FRAMES mode, we need to store the transformed vertex positions
                    transformed_vertices = [(v.index, source.matrix_world @ v.co) for v in source.data.vertices]
                    eval_mesh = source.data
                    if context.scene.lm_tw_mode == 'FRAMES':
                        # Evaluate the object to get the transformed vertex positions
                        bpy.context.scene.frame_current = frame.frame_number
                        
                        depsgraph = bpy.context.evaluated_depsgraph_get()
                        eval_obj = source.evaluated_get(depsgraph)
                        eval_mesh = eval_obj.data
                        # Store original indices and transformed positions
                        transformed_vertices = [(v.index, source.matrix_world @ v.co) for v in eval_mesh.vertices]
                   
                    drawing = None #compatibilty with 4.2/4.4
                    if is_GP3(): 
                         # For Blender 4.3 and later
                        drawing = frame.drawing
                    else: 
                        drawing = frame                  

                    # Loop through all strokes in this frame
                    for stroke_idx, stroke in enumerate(drawing.strokes):
                        # Get stroke points world coordinates
                        stroke_points_co = None
                        stroke_offset = None
                        if is_GP3():
                            # For Blender 4.3 and later we need the stroke offset
                            stroke_points_co = [target.matrix_world @ point.position for point in stroke.points] 
                            stroke_offset = drawing.curve_offsets[stroke_idx].value
                        else:   
                            stroke_points_co = [target.matrix_world @ point.co for point in stroke.points]
                        print("Processing stroke ", stroke_idx+1, "/",len(drawing.strokes)," in frame ", frame.frame_number)

                        # For each point in the stroke
                        for point_idx, point_co in enumerate(stroke_points_co):

                            closest_vert_index = None
                            closest_face_verts = None
                            if context.scene.lm_tw_nearest == 'VERTEX':
                                # Find closest vertex in source mesh (the function will take care of the difference between current and animated positions)                           
                                closest_vert_index = find_nearest_vertex(point_co, transformed_vertices)                            
                            else:
                                closest_face_verts = find_nearest_face(point_co, source)

                            
                            # Transfer weights from closest vertex
                            if closest_vert_index or closest_face_verts:
                                for group in target.vertex_groups:
                                    if group.lock_weight:
                                        # Skip locked vertex groups
                                        continue

                                    if not group.name in source.vertex_groups:
                                        # Skip if source does not have this vertex group
                                        continue

                                    weight = None
                                    try:
                                        if context.scene.lm_tw_nearest == 'VERTEX':
                                            weight = source.vertex_groups[group.name].weight(closest_vert_index)
                                        else:
                                            # For face nearest, we need to average the weights of the vertices of the face
                                            weight = sum(source.vertex_groups[group.name].weight(v_index) for v_index in closest_face_verts) / len(closest_face_verts)
                                    except RuntimeError:
                                        # If the vertex is not in the group, weight will raise an error
                                        weight = 0.0
                                    
                                    # Add weight to the corresponding vertex group in target
                                    if is_GP3():

                                        # For Blender 4.3 and later we need to create an attribute to store the weight, and then transfer it to the vertex group (they need different names)
                                        temp_attr_name = temp_attr_prefix + group.name

                                        attr = drawing.attributes.get(temp_attr_name)
                                        if not attr:
                                            # Create attribute if it does not exist
                                            attr = drawing.attributes.new(name=temp_attr_name, type='FLOAT', domain='POINT')
                                        
                                        # Assign weight
                                        if hasattr(attr,"data"): # just in case
                                            attr.data[stroke_offset + point_idx].value = weight
                                    else:
                                        # For Blender 4.2 and earlier we can directly set the weight
                                        stroke.points.weight_set(vertex_group_index=group.index, point_index=point_idx, weight=weight)

                                    if context.scene.lm_tw_mode == 'FRAMES':
                                        # we need to apply the transformation to the stroke point
                                        delta = None
                                        if context.scene.lm_tw_nearest == 'VERTEX':
                                            # Get the difference between original and transformed position (nearest point)
                                            original_pos = source.matrix_world @ source.data.vertices[closest_vert_index].co
                                            transformed_pos = next(pos for idx, pos in transformed_vertices if idx == closest_vert_index)
                                            delta = transformed_pos - original_pos
                                        else:
                                            # Calculate average of vertex positions for the face
                                            delta = mathutils.Vector((0,0,0))
                                            for v_index in closest_face_verts:
                                                original_pos = source.matrix_world @ source.data.vertices[v_index].co
                                                transformed_pos = next(pos for idx, pos in transformed_vertices if idx == v_index)
                                                delta += (transformed_pos - original_pos)
                                            delta /= len(closest_face_verts)

                                        # Apply inverse transformation to stroke point
                                        if is_GP3():
                                            stroke.points[point_idx].position = target.matrix_world.inverted() @ (point_co - delta)
                                        else:
                                            stroke.points[point_idx].co = target.matrix_world.inverted() @ (point_co - delta)
                                        

            # If we are in Blender 4.3 or later, we need to copy the temporary attributes to the vertex groups
            if is_GP3():
                for vgroup in target.vertex_groups:
                    # Check if we have data to transfer for this vertex group
                    tmp_attr_name = temp_attr_prefix + vgroup.name      
                    if tmp_attr_name in target.data.layers[0].frames[0].drawing.attributes: # we can check the first frame of the first layer, as all frames should have the same attributes
                        # print("Transferring vertex group:", vgroup.name)
                        # Copy the attribute to the vertex group with the temporary name
                        self.copy_attribute_using_geometry_nodes(target, tmp_attr_name, vgroup.name, (context.scene.lm_tw_mode == 'CURRENT')) # if we are in CURRENT mode, we want to apply the modifier to the top of the stack
                        # After copying, we can remove the temporary attribut
                        for layer in target.data.layers:
                            for frame in layer.frames:
                                # Remove the temporary attribute from the drawing
                                if tmp_attr_name in frame.drawing.attributes:                                    
                                    frame.drawing.attributes.remove(frame.drawing.attributes[tmp_attr_name])

            print("Weight transfer completed successfully.")

        except Exception as e:
            import traceback
            traceback.print_exc()

            self.report({'WARNING'}, "Unable to transfer weights: " + str(e))
            return {'CANCELLED'}

        return {'FINISHED'}