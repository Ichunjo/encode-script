"""Magia Record S2 Script"""
import vapoursynth as vs
from debandshit import dumb3kdb, placebo_deband
from vardautomation import FileInfo, PresetEAC3, PresetWEB, VPath
from vardefunc.aa import Eedi3SR
from vardefunc.mask import MinMax, SobelStd
from vardefunc.misc import DebugOutput, merge_chroma
from vardefunc.noise import Graigasm
from vardefunc.scale import to_444
from vardefunc.types import DuplicateFrame as DF
from vardefunc.util import (finalise_output, initialise_input, replace_ranges,
                            select_frames)
from vsutil import depth, get_y, split

from magia_common import Denoise, Encoding, Mask, Thr, graigasm_args

core = vs.core


NUM = __file__[-5:-3]


# WEB_CRU = FileInfo(
#     f'eps/Magia Record S2 - {NUM} (Crunchyroll 1080p).mkv',
#     preset=PresetWEB
# )
WEB_FUN = FileInfo(
    list(VPath('eps/').glob(f'[[]SubsPlease[]] *{NUM}*.mkv')).pop(),
    (168, None),
    preset=PresetWEB
)
WEB_AMZ = FileInfo(
    list(VPath('eps/').glob(f'Magia Record S2 - {NUM} (Amazon*.mkv')).pop(),
    None,
    preset=(PresetWEB, PresetEAC3)
)
WEB_BIL = FileInfo(
    list(VPath('eps/').glob(f'[[]NC-Raws[]] 魔法纪录 魔法少女小圆外传 第二季 －觉醒前夜－ - {NUM}*.mkv')).pop(),
    None,
    preset=PresetWEB
)
WEB_FUN.num_prop = True
WEB_AMZ.num_prop = True
WEB_BIL.num_prop = True
import lvsfunc

DEBUG = DebugOutput(
    # CR=WEB_CRU.clip_cut,
    # Funimation=WEB_FUN.clip_cut,
    # Bilibili=WEB_BIL.clip_cut.resize.Bicubic(1920, 1080, format=vs.YUV420P8),
    # AMZ=WEB_AMZ.clip_cut.resize.Bicubic(1920, 1080),
    # FUN_Bili=lvsfunc.comparison.stack_compare(WEB_FUN.clip_cut, WEB_BIL.clip_cut.resize.Bicubic(1920, 1080, format=vs.YUV420P8), make_diff=True, height=540),
    # Funi_AMZ=lvsfunc.comparison.stack_compare(WEB_FUN.clip_cut, WEB_AMZ.clip_cut.resize.Bicubic(1920, 1080), make_diff=True, height=540),
    num=9, props=7
)

# # AMAZON TRIMS
WEB_AMZ.trims_or_dfs = [
    # (0, 3237), DF(3237, 1), (3237, 33925)
    (0, 3237), (3237, 33925)
]
# AMAZON TRIMS | fill for the endcard
WEB_AMZ.trims_or_dfs += [
    DF(0, 34046 - WEB_AMZ.clip_cut.num_frames)
]
# BILIBILI TRIMS
WEB_BIL.trims_or_dfs = [
    (0, 3237), DF(3237, 55), (3237, None)
]
WEB_BIL.trims_or_dfs += [
    DF(0, 34046 - WEB_BIL.clip_cut.num_frames)
]


DEBUG <<= dict(
    # Funi=WEB_FUN.clip_cut,
    # Funi_Bili=lvsfunc.comparison.stack_compare(WEB_FUN.clip_cut, WEB_BIL.clip_cut.resize.Bicubic(1920, 1080, format=vs.YUV420P8), make_diff=True, height=540),
    # Funi_AMZ=lvsfunc.comparison.stack_compare(WEB_FUN.clip_cut, WEB_AMZ.clip_cut.resize.Bicubic(1920, 1080), make_diff=True, height=540),
    Bilibili=WEB_BIL.clip_cut.resize.Bicubic(1920, 1080, format=vs.YUV420P8),
    Amazon=WEB_AMZ.clip_cut.resize.Bicubic(1920, 1080),
)


class Filtering:
    # @DEBUG.catch(op='@=')
    @finalise_output
    @initialise_input(bits=32)
    def main(self, src: vs.VideoNode = WEB_BIL.clip_cut) -> vs.VideoNode:
        # debug = DEBUG
        pre = get_y(src)
        aaa = Eedi3SR(
            nnedi3cl=True, gamma=40, nrad=2, mdis=15,
            mclip=SobelStd().get_mask(pre, lthr=0.07, multi=1.75).std.Maximum().std.Minimum()
        ).do_aa()(pre)
        # debug @= mask
        aaa = merge_chroma(aaa, src)
        out = aaa
        # out = src

        amz_clip = depth(WEB_AMZ.clip, 32)
        endcard = core.average.Mean(
            [select_frames(amz_clip, [f])
             for f in range(34165, WEB_AMZ.clip.num_frames)]
        )
        endcard = to_444(endcard, None, None, True, False).resize.Point(format=vs.RGBS, matrix_in=1)
        endcard_ups = core.w2xnvk.Waifu2x(endcard, 0, 2, precision=32)
        endcard = replace_ranges(out, endcard_ups*out.num_frames, [(33926, None)], mismatch=True)
        out = endcard

        rescale = out.resize.Bicubic(
            1920, 1080, vs.YUV444PS,
            matrix=1,
            filter_param_a=-0.5, filter_param_b=0.25,
            filter_param_a_uv=0, filter_param_b_uv=0.5
        )
        out = rescale

        denoise = Denoise.bm3d(out, [1.0, 1.5, 1.5], radius=1, profile='fast')
        out = denoise

        out = depth(out, 16)


        import G41Fun as gf
        dehalo = gf.MaskedDHA(out, 2.0, 2.0, 0, 1.0)
        out = replace_ranges(out, dehalo, [(33926, None)])


        deband_mask = Mask().lineart_deband_mask(
            denoise.rgsf.RemoveGrain(3), brz_rg=2200/65536, brz_ed=1700/65536, brz_ed_ret=12000/65536,
            ret_thrs=Thr(lo=(17 - 16) / 219, hi=(18 - 16) / 219)
        )
        deband_mask = core.std.Expr(
            split(deband_mask) + [get_y(rescale)],
            f'a {(18-16)/219} > x y z max max 65535 * 0 ?', vs.GRAY16
        ).rgvs.RemoveGrain(3).rgvs.RemoveGrain(22).rgvs.RemoveGrain(11)
        deband_mask = core.std.Lut(deband_mask, function=lambda x: x if x > 15000 else 0)
        # debug[10] = deband_mask
        # debug <<= MinMax._minmax(deband_mask, 10, core.std.Maximum).std.BoxBlur(0, 4, 4, 4, 4)

        db3k = dumb3kdb(out, 20, [45, 40], grain=30)
        db3k_masked = core.std.MaskedMerge(db3k, out, deband_mask)
        # dbpl = placebo_deband(out, 18, 7.5, grain=2.0)
        db3kmore = dumb3kdb(out, 20, 49, grain=30)
        deband_a = core.std.MaskedMerge(
            db3kmore, db3k,
            MinMax._minmax(deband_mask, 10, core.std.Maximum).std.BoxBlur(0, 4, 4, 4, 4)
        )
        deband_b = core.std.MaskedMerge(deband_a, out, deband_mask)
        deband = core.std.Expr(
            [deband_b, out, db3k_masked],
            [f'y {30<<8} < z x ?', 'z']
        )
        dbpl = placebo_deband(out, 25, 7.5, iterations=3, grain=2.0)
        deband = replace_ranges(deband, core.std.MaskedMerge(dbpl, deband, deband_mask), [(3237, 3395)])
        out = deband

        grain = Graigasm(**graigasm_args).graining(out)  # type: ignore
        out = grain

        return out


if __name__ == '__main__':
    del DEBUG
    FINAL_FILE = WEB_BIL
    FINAL_FILE.path = WEB_AMZ.path
    FINAL_FILE.clip = WEB_AMZ.clip_cut
    FINAL_FILE.a_src = WEB_AMZ.a_src
    FINAL_FILE.a_src_cut = WEB_AMZ.a_src_cut
    FINAL_FILE._trims_or_dfs = WEB_AMZ._trims_or_dfs
    zones = {
        (3237, 3395-1): {"b": 1.8}
    }
    Encoding(FINAL_FILE, Filtering().main(), NUM).run(zones=zones, upload_ftp=True)
else:
    Filtering().main()
    pass
