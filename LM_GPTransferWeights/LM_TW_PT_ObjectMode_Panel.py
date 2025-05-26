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

# N panel menu in object mode

import bpy

class LM_TW_PT_ObjectMode_Panel(bpy.types.Panel):
    bl_idname = "LM_TW_PT_ObjectMode_Panel"
    bl_label = "GP Transfer Weights"
    bl_category = "Grease Pencil"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"


    bpy.types.Scene.lm_tw_source_mesh = bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Source Mesh",
        description="Source mesh object to transfer weights from"
    )

    bpy.types.Scene.lm_tw_target_gp = bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Target Grease Pencil",
        description="Target grease pencil object to transfer weights to"
    )
    bpy.types.Scene.lm_tw_distance = bpy.props.FloatProperty(
        name="Max distance",
        description="Maximum distance for weight transfer. Set to 0.0 to disable distance check.",
        default=0,
        min=0.0,
        soft_max=10.0,
        unit='LENGTH'
    )
    bpy.types.Scene.lm_tw_mode = bpy.props.EnumProperty(
        name="Mode",
        description="Weight transfer mode",
        items=[
            ('CURRENT', "Original", "Evaluate all GP frames on mesh original position"),
            ('FRAMES', "Each frame (slow, changes drawings)", "Evaluate GP frames on mesh animated frame"),
            
        ],
        default='CURRENT'
    )
    bpy.types.Scene.lm_tw_nearest = bpy.props.EnumProperty(
        name="Find nearest",
        description="Weight transfer algorithm",
        items=[
            ('VERTEX', "Vertex (Faster)", "Weight of the nearest vertex on the mesh"),
            ('FACE', "Face (Slower)", "Weight intepolation of the vertices of the nearest face on the mesh"),
            
        ],
        default='VERTEX'
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT')
    
    def draw(self, context):    
        layout = self.layout

        # mesh input box
        layout.label(text="Source mesh:")
        layout.prop_search(context.scene, "lm_tw_source_mesh", bpy.data, "objects", text="")

        # grease pencil input box
        layout.label(text="Target Grease Pencil:")
        layout.prop_search(context.scene, "lm_tw_target_gp", bpy.data, "objects", text="")

        # delete button        
        layout.operator("lm_tw.delete")

        # transfer button
        layout.label(text= "Weight transfer options")
        #this is not implemented yet
        #layout.prop(context.scene, "lm_tw_nearest", expand=True)        
        layout.prop(context.scene, "lm_tw_mode", expand=True)
        layout.prop(context.scene, "lm_tw_distance")
        layout.label(text= "Transfer")
        layout.operator("lm_tw.transfer")
          