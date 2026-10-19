# Review-only directory modal job. Not installed by this source file.
# Entry ABI: row transition r25=scene. Job ABI: r24=scene, root stack frame.
.text
.globl directory_enter,directory_job,directory_context,directory_cleanup
directory_enter:
    lis 11,directory_context@ha
    addi 11,11,directory_context@l
    stw 25,0(11)
    li 0,0
    stw 0,4(11)
    stw 0,8(11)
    stw 0,12(11)
    li 3,0x53b
    b native_row_resume

directory_job:
    # Preserve the native callback's locals; frame/cursor live in its stack.
    mr 4,1
    stwu 1,-64(1)
    mflr 0
    stw 0,68(1)
    stmw 26,40(1)
    mr 26,4
    lis 31,0x8039
    addi 31,31,-0x5df0
    lis 30,directory_context@ha
    addi 30,30,directory_context@l
    lwz 0,0(30)
    cmpw 0,24
    bne directory_done
    lwz 0,0x2bc(31)
    cmpwi 0,4
    bne directory_cancel
    lwz 0,0x2c0(31)
    cmpwi 0,4
    bne directory_cancel
    lwz 3,0x248(31)
    cmpwi 3,0
    beq directory_done
    lwz 0,0xac(3)
    cmpwi 0,0
    bne directory_done
    lwz 29,0x24c(31)
    cmpwi 29,0
    beq directory_return
    lwz 0,4(30)
    cmpwi 0,0
    bne directory_update
    lwz 0,0(29)
    cmpwi 0,0
    bne directory_return
    lwz 0,4(29)
    cmpwi 0,0
    beq directory_find
    cmpwi 0,3
    beq directory_find
    cmpwi 0,4
    bne directory_return
directory_find:
    mr 3,24
    lwz 4,0x1a8(24)
    bl native_selected_shop
    cmpwi 3,0
    beq directory_return
    mr 28,3
    bl native_shop_id
    cmpwi 3,0
    beq directory_return
    lis 4,directory_prefix@ha
    addi 4,4,directory_prefix@l
directory_id:
    lbz 0,0(4)
    cmpwi 0,0
    beq directory_description
    lbz 5,0(3)
    cmpw 0,5
    bne directory_return
    addi 4,4,1
    addi 3,3,1
    b directory_id
directory_description:
    # The row stores converted UTF-16 description at +0x18.
    lwz 28,0x18(28)
    cmpwi 28,0
    beq directory_return
    mr 4,28
    li 27,0
directory_length:
    lhz 0,0(4)
    cmpwi 0,0
    beq directory_text
    addi 27,27,1
    cmplwi 27,512
    bgt directory_return
    addi 4,4,2
    b directory_length
directory_text:
    cmpwi 27,0
    beq directory_return
    lwz 3,0x1e0(29)
    cmpwi 3,0
    beq directory_return
    lwz 12,0(3)
    lwz 12,0x3c(12)
    lis 4,directory_group@ha
    addi 4,4,directory_group@l
    li 5,1
    mtctr 12
    bctrl
    cmpwi 3,0
    beq directory_return
    stw 3,8(30)
    lwz 12,0(3)
    lwz 12,0x3c(12)
    lis 4,directory_body@ha
    addi 4,4,directory_body@l
    li 5,1
    mtctr 12
    bctrl
    cmpwi 3,0
    beq directory_return
    stw 3,12(30)
    lwz 12,0(3)
    lwz 12,0x74(12)
    addi 4,27,1
    mtctr 12
    bctrl
    lwz 3,12(30)
    lwz 12,0(3)
    lwz 12,0x7c(12)
    mr 4,28
    li 5,0
    mtctr 12
    bctrl
    mr 3,29
    li 4,0x101
    li 5,0
    bl native_open_dynamic
    lis 4,directory_geometry@ha
    addi 4,4,directory_geometry@l
    lfs 0,0(4)
    lwz 3,0x218(29)
    stfs 0,0x50(3)
    lwz 3,0x21c(29)
    stfs 0,0x50(3)
    lfs 0,4(4)
    lwz 3,0x17c(29)
    stfs 0,0x30(3)
    lwz 3,0x1a0(29)
    stfs 0,0x30(3)
    lwz 3,0x1c4(29)
    stfs 0,0x30(3)
    lwz 3,8(30)
    lbz 0,0xbb(3)
    ori 0,0,1
    stb 0,0xbb(3)
    li 0,1
    stw 0,4(30)
    b directory_draw
directory_update:
    mr 3,29
    addi 4,26,0xa0
    addi 5,26,0x40
    bl native_modal_update
    lwz 0,0(29)
    cmpwi 0,0
    beq directory_return
directory_draw:
    mr 3,24
    addi 4,26,0xa0
    li 5,0
    li 6,30
    bl native_draw_list
    mr 3,29
    addi 4,26,0xa0
    bl native_modal_draw
    b directory_done
directory_cancel:
    lwz 0,4(30)
    cmpwi 0,0
    beq directory_clear
    lwz 3,0x24c(31)
    cmpwi 3,0
    beq directory_clear
    li 0,0
    stw 0,4(3)
    li 4,0
    li 5,0
    bl native_modal_update
directory_clear:
    bl directory_hide
    li 0,0
    stw 0,0(30)
    stw 0,4(30)
    b directory_done
directory_return:
    bl directory_hide
    li 0,0
    stw 0,0(30)
    stw 0,4(30)
    mr 3,24
    lwz 4,0x1a8(24)
    li 5,0
    li 6,1
    bl native_reset_row
    li 0,0xfa
    stw 0,0x10(24)
directory_done:
    lmw 26,40(1)
    lwz 0,68(1)
    mtlr 0
    addi 1,1,64
    b native_job_exit
.balign 4
directory_hide:
    lwz 3,8(30)
    cmpwi 3,0
    beq directory_hidden
    lbz 0,0xbb(3)
    rlwinm 0,0,0,24,30
    stb 0,0xbb(3)
directory_hidden:
    li 0,0
    stw 0,8(30)
    stw 0,12(30)
    blr
.balign 4
directory_cleanup:
    stwu 1,-160(1)
    mflr 0
    stw 0,164(1)
    mfcr 0
    stw 0,8(1)
    mfctr 0
    stw 0,12(1)
    stmw 3,16(1)
    lis 30,directory_context@ha
    addi 30,30,directory_context@l
    lwz 0,0(30)
    cmpw 0,3
    bne directory_cleanup_done
    lwz 0,4(30)
    cmpwi 0,0
    beq directory_cleanup_hide
    lis 3,0x8039
    addi 3,3,-0x5df0
    lwz 3,0x24c(3)
    cmpwi 3,0
    beq directory_cleanup_hide
    li 0,0
    stw 0,4(3)
    li 4,0
    li 5,0
    bl native_modal_update
directory_cleanup_hide:
    bl directory_hide
    li 0,0
    stw 0,0(30)
    stw 0,4(30)
directory_cleanup_done:
    lwz 0,8(1)
    mtcrf 255,0
    lwz 0,12(1)
    mtctr 0
    lmw 3,16(1)
    lwz 0,164(1)
    mtlr 0
    addi 1,1,160
    stwu 1,-128(1)
    b native_cleanup_resume
.balign 4
directory_context:
    .long 0,0,0,0
directory_prefix:
    .asciz "hotpepper:"
.balign 4
directory_group:
    .asciz "JWC24_DIRECTORY"
directory_body:
    .asciz "JWC24_DIR_BODY"
.balign 4
directory_geometry:
    .float 330.0,-182.0
.balign 4
