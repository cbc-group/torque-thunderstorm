args = getArgument();
parts = split(args, ',');

// check whether we have 3d calibration file
cal_z = false;
z_cal_path = "";
if (parts.length > 1) {
    print("3D mode");
    cal_z = true;
    z_cal_path = parts[1];
    if (parts.length > 2) {
        print("Unused arguments detected");
    }
} else {
    print("2D mode");
}
// retrieve the workspace directory
ws_dir = parts[0];

// hide active images
setBatchMode(true);

print("Working under \"" + ws_dir + "\"");

// get all the files
file_list = getFileList(ws_dir);

// iterate through the files
for(i = 0; i < file_list.length; i++) {
    // generate the full path
    in_path = ws_dir + "/" + file_list[i];
    print(in_path);

    // generate result CSV file path
    fname = split(file_list[i], '.');
    out_path = ws_dir + "/" + fname[0] + ".csv";

    open(in_path);

    setcam();

    if (cal_z) {
        proc3d(out_path, z_cal_path);
    } else {
        proc2d(out_path);
    }

    run("Close All");
}

// restore settings
setBatchMode(false);
// quit Fiji
run("Quit");

macro "Close All Windows" {
    while (nImages > 0) {
        selectImage(nImages);
        close();
    }
}

function setcam() {
    run("Camera setup", "readoutnoise=1.64 offset=80.0 quantumefficiency=0.7 isemgain=false photons2adu=0.47 pixelsize=125.4");
}

function proc2d(out_path) {
    run("Run analysis", "filter=[Wavelet filter (B-Spline)] scale=2.0 order=3 detector=[Local maximum] connectivity=8-neighbourhood threshold=1.5*std(Wave.F1) estimator=[PSF: Integrated Gaussian] sigma=1.6 fitradius=4 method=[Maximum likelihood] full_image_fitting=false mfaenabled=false renderer=[Averaged shifted histograms] magnification=5.0 colorize=false threed=false shifts=2 repaint=50");
    run("Export results", "floatprecision=1 filepath=" + out_path + " fileformat=[CSV (comma separated)] sigma=true intensity=true offset=true saveprotocol=false x=true y=true bkgstd=true id=false uncertainty_xy=true frame=true");
}

function proc3d(out_path, z_cal_path) {
    run("Run analysis", "filter=[Wavelet filter (B-Spline)] scale=2.0 order=3 detector=[Local maximum] connectivity=8-neighbourhood threshold=1.5*std(Wave.F1) estimator=[PSF: Elliptical Gaussian (3D astigmatism)] sigma=1.6 fitradius=4 method=[Maximum likelihood] calibrationpath=[" + z_cal_path + "] full_image_fitting=false mfaenabled=false renderer=[Averaged shifted histograms] magnification=5.0 colorize=false threed=false shifts=2 repaint=50");
    run("Export results", "floatprecision=1 filepath=" + out_path + " fileformat=[CSV (comma separated)] offset=true saveprotocol=false bkgstd=true uncertainty_xy=true intensity=true x=true sigma2=true uncertainty_z=true y=true sigma1=true z=true id=false frame=true");
}
