from PySide6.QtWidgets import QMessageBox, QFileDialog, QApplication
import numpy as np
import sys
from pandas import DataFrame

decimals_excel = 2


def show_dialog(title, msg):
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setText(msg)
    msg_box.setWindowTitle(title)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

    return_value = msg_box.exec()


def question_dialog(title, msg):
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Question)
    msg_box.setText(msg)
    msg_box.setWindowTitle(title)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

    return_value = msg_box.exec()
    if (return_value == QMessageBox.StandardButton.Yes) or (return_value == QMessageBox.StandardButton.Cancel):
        return True
    else:
        return False


def save_data_to_acp(file_path, fp_data, test_type, dt_string, bodyweight, fs, athlete_name='', ext_weight='0',
                     description=''):
    time = fp_data['Time (s)']
    n_samples = len(time)
    v_keys = ['Time (s)', 'Raw Fx (N)', 'Raw Fy (N)', 'Raw Fz (N)', 'Raw Mx (N m)', 'Raw My (N m)', 'Raw Mz (N m)']
    with open(file_path, "w+") as file1:
        file1.write(test_type)
        file1.write('\n\n')
        file1.write(dt_string)
        file1.write('\n\n')
        file1.write(f"{n_samples} @ {fs}\t(number of samples, data rate) Filter: 0")
        file1.write('\n\n')
        file1.write(f"{bodyweight}\t(body weight)")
        file1.write('\n\n')
        file1.write("SI units")
        file1.write('\n\n')
        file1.write(f"Athlete: {athlete_name}")
        file1.write('\n\n')
        file1.write(f"External Weight: {ext_weight}")
        file1.write('\n\n')
        file1.write(f"Description: {description}")
        file1.write('\n\n')
        file1.write(f"{v_keys[0]}")
        for i in range(1, len(v_keys)):
            file1.write(f"\t{v_keys[i]}")
        file1.write('\n\n')
        for j in range(n_samples):
            file1.write(f"{np.round(time[j], 3)}")
            for k in range(1, len(v_keys)):
                file1.write(f"\t{fp_data[v_keys[k]][j]}")
            file1.write('\n\n')


def open_file_acp2(file_path):
    with open(file_path, 'r') as f:
        pp = False
        proc = False
        pp_dic = {}
        proc_dic = {}
        for line_str in f:
            if ("Preprocessed Variables" in line_str):
                pp = True
            elif ("Processed Variables" in line_str):
                pp = False
                proc = True
            else:
                if line_str != '\n':
                    line_str = line_str.replace('\t', '').replace('\n', '')
                    key = line_str.split(':')[0]
                    val_str = line_str.split(':')[-1].replace(' ', '')
                    try:
                        val = float(val_str)
                        if val.is_integer():
                            val = int(val)
                    except ValueError:
                        val = val_str
                    if pp:
                        pp_dic[key] = val
                    elif proc:
                        proc_dic[key] = val
    return pp_dic, proc_dic


def save_data_to_acp2(file_path, pp_dic, proc_dic):
    with open(file_path, "w+") as file1:
        file1.write('Preprocessed Variables\n\n')
        for key in pp_dic.keys():
            file1.write(f"\t{key}: {pp_dic[key]}\n")
        file1.write('\n')
        file1.write('Processed Variables\n\n')
        for key in list(proc_dic.keys()):
            file1.write(f"\t{key}: {proc_dic[key]}\n")


def closest_value_idx(array, value):
    idx = (np.abs(array - value)).argmin()
    return idx


def read_file_dialog(title="Open File", file_type="All Files"):
    if file_type == "All Files":
        type_filter = "All Files (*)"
    else:
        type_filter = file_type + " (*." + file_type + ")"
    options = QFileDialog.Options()
    options |= QFileDialog.Option.DontUseNativeDialog
    file_name, _ = QFileDialog.getOpenFileName(None, title, "", type_filter, options=options)
    return file_name


def read_folder_dialog(title="Open folder"):
    app = QApplication(sys.argv)
    qfd = QFileDialog()
    folder_path = QFileDialog.getExistingDirectory(qfd, title, "")
    return folder_path


def save_file_dialog(title="Save file as"):
    options = QFileDialog.Options()
    options |= QFileDialog.Option.DontUseNativeDialog
    file_name = QFileDialog.getSaveFileName(None, title, options=options)
    return file_name[0]


def read_force_file(file_path, all_var=False):
    i = 1
    var_names = []
    description = ''
    data_type = 'Free Mode'
    with open(file_path, 'r') as f:
        first = True
        for line_str in f:
            if first:
                if ("Countermovement" in line_str) or ("CMJ" in line_str):
                    data_type = "CMJ"
                elif ("Weighted" in line_str) or ("WSJ" in line_str):
                    data_type = "WSJ"
                elif ("Squat" in line_str) or ("SJ" in line_str):
                    data_type = "SJ"
                elif ("ISO" in line_str) or ("IMTP" in line_str):
                    data_type = "ISO"
                else:
                    data_type = line_str.split('\n')[0].split('(')[-1].split(')')[0]
                first = False
            elif 'Time (s)' in line_str:
                var_names = line_str.split(f'\n')[0].split(f'\t')
                break
            elif all_var:
                if ('-' in line_str) and (':' in line_str):
                    dt_string = line_str
                elif '@' in line_str:
                    fs = int(line_str.split('@')[-1].split('(')[0].replace(' ', ''))
                elif 'Description: ' in line_str:
                    description = line_str.replace('Description: ', '')
            i += 1
    force_data_arr = np.loadtxt(file_path, skiprows=i)
    force_data_dic = {}
    for key in var_names:
        force_data_dic[key] = force_data_arr[:, var_names.index(key)]

    if all_var:
        return force_data_dic, var_names, data_type, dt_string, fs, description
    else:
        return force_data_dic, var_names, data_type


def create_export_data_frame(data_dic, trial_txt, test_type):
    cols = []
    values = []

    cols.append('Trial')
    values.append(trial_txt)
    cols.append('Type')
    values.append(test_type)

    for key, value in data_dic.items():
        cols.append(key)
        if type(value) is str:
            values.append(value)
        else:
            if 'duration' in key:
                values.append(np.round(value, 5))
            elif 'time_of_flight' == key:
                values.append(np.round(value, 5))
            elif 'movement_time' == key:
                values.append(np.round(value, 5))
            else:
                values.append(np.round(value, decimals_excel))

    data_df = DataFrame(np.matrix(values), columns=cols)

    return data_df


def fix_processing_output(data_dic, trial_txt, test_type):
    data_dic_out = {
        'Trial': trial_txt,
        'Type': test_type
    }
    for key, value in data_dic.items():
        if type(value) is not str:
            if 'duration' in key:
                data_dic_out[key] = np.round(value, 5)
            elif 'time_of_flight' == key:
                data_dic_out[key] = np.round(value, 5)
            elif 'movement_time' == key:
                data_dic_out[key] = np.round(value, 5)
            else:
                data_dic_out[key] = np.round(value, decimals_excel)
    return data_dic_out


def get_data_from_acp(file_path):
    fp_data, var_names, data_type = read_force_file(file_path)
    force = fp_data['Raw Fz (N)']
    time = fp_data['Time (s)']
    fs = int(1 / (time[1] - time[0]))
    return force, time, fs, data_type
