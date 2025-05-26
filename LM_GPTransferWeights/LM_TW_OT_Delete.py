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

# Delete weights of grease pencil strokes

import bpy

class LM_TW_OT_Delete(bpy.types.Operator):
    """Delete all unlocked weights of grease pencil target object"""
    bl_idname = "lm_tw.delete"
    bl_label = "Delete all unlocked weights"
    bl_description = "Delete all unlocked weights of grease pencil target object"
    bl_options = {'REGISTER', 'UNDO'}

    # main function
    def execute(self, context):
        
        try:
            
            target = context.scene.lm_tw_target_gp

            if target is None:
                raise ValueError("No target object selected")

            if target.type != 'GPENCIL' and target.type != 'GREASEPENCIL':
                raise ValueError("Target must be a grease pencil object")
            
            print("Deleting unlocked weights from", target.name)

            # Get all vertex groups from gpencil object
            vgroups = target.vertex_groups

            # Ensure target has matching vertex groups
            for vgroup in vgroups:
                if not vgroup.lock_weight:
                    print("Deleting unlocked vertex group:", vgroup.name)
                    
                    for layer in target.data.layers:
                        for frame in layer.frames:
                            if hasattr(frame, 'drawing') and frame.drawing.attributes.get(vgroup.name):
                                # Remove the vertex group attribute from the drawing
                                frame.drawing.attributes.remove(frame.drawing.attributes[vgroup.name])

                    target.vertex_groups.remove(vgroup)

            print("All unlocked weights deleted from", target.name)


        except Exception as e:
            import traceback
            traceback.print_exc()

            self.report({'WARNING'}, "Unable to delete weights: " + str(e))
            return {'CANCELLED'}

        return {'FINISHED'}