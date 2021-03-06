# -*- encoding:utf-8 -*-
# @Time    : 2019/5/13 10:58
# @Author  : gfjiang
# @Site    : 
# @File    : ECGProcess.py
# @Software: PyCharm
import numpy as np
import pandas as pd


class ECGProcess:
    def __init__(self, ecg_data):
        self.ecg_data = ecg_data
        pass

    def cal_extreme_max_point(self, x):
        data_max_index = len(x) - 1
        max_value = 0.
        max_value_index = np.argmax(x)
        if 0 < max_value_index < data_max_index:
            max_value = x[max_value_index]
        return max_value_index, max_value

    def cal_extreme_point(self, x):
        data_max_index = len(x) - 1
        max_value = 0.  # 注意这里不能初始化成0, 否则后面值会被自动转成int
        min_value = 0.
        max_value_index = np.argmax(x)
        min_value_index = np.argmin(x)
        if 0 < max_value_index < data_max_index:
            max_value = x[max_value_index]
        if 0 < min_value_index < data_max_index:
            min_value = x[min_value_index]
        return max_value_index, max_value, min_value_index, min_value

    def get_adjacent_rows(self, x_row, x):
        max_point_index = np.argwhere(x == x_row)
        if max_point_index.shape == (1, 2):
            temp = max_point_index[0, 0]
            return temp - 1, temp, temp + 1
        return 0, 0, 0

    # 找极值点
    def get_extreme_point(self, ECG):
        window_len = 20  # 此参数与overlap之间有一个限制， window_len*overlap>1
        import more_itertools as mit
        window_data = np.array([list(w) for w in
                                mit.windowed(ECG.values,
                                             n=window_len,
                                             fillvalue=np.nan,
                                             step=int(window_len * 0.9))])
        temp = ~np.isnan(window_data).any(axis=1)
        window_data = window_data[temp]
        extreme_points = np.apply_along_axis(self.cal_extreme_point, 1, window_data)
        # 调试画图时显示用
        # extreme_max = pd.DataFrame(extreme_points[..., 1],
        #                            index=extreme_points[..., 0].astype(np.int), columns=['max'])
        # extreme_min = pd.DataFrame(extreme_points[..., 3],
        #                            index=extreme_points[..., 2].astype(np.int), columns=['min'])
        window_index = np.arange(len(extreme_points))
        window_index = window_index.repeat(2).reshape((-1, 2))
        extreme_points[..., [0, 2]] += (window_index * (window_len * 0.9))
        return extreme_points

    def get_R(self, ECG, overlap=0.9):
        """
        找R点
        :param ECG:
        :param overlap:
        :return:
        """
        # 设计一个overlap参数可以缓解丢点情况
        import more_itertools as mit
        window_len = 1200  # 超参数
        window_data = np.array([list(w) for w in mit.windowed(
            ECG.values, n=window_len, fillvalue=np.nan, step=int(window_len * overlap))])
        # 初步提取R点
        extreme_max_points_1500 = np.apply_along_axis(self.cal_extreme_max_point, 1, window_data)
        window_index = np.arange(len(extreme_max_points_1500))
        # 对应关系很重要，否则索引不正确。初步提取的R点在索引跟新前无能做任何去除或增加操作
        extreme_max_points_1500[..., 0] += (window_index * (window_len * overlap))

        # 根据幅值筛选
        extreme_max_points_1500 = extreme_max_points_1500[~np.isnan(extreme_max_points_1500).any(axis=1)]
        # temp = extreme_max_points_1500[:, 1] > 0.2
        extreme_max_points_1500 = extreme_max_points_1500[extreme_max_points_1500[:, 1] > 0.2]

        T_R = self.get_T_R(pd.DataFrame(extreme_max_points_1500[..., 0]))
        # T_R = pd.DataFrame(extreme_max_points_1500[..., 0]) - \
        #        pd.DataFrame(extreme_max_points_1500[..., 0]).shift(1)

        # 滤除杂点
        T_R.fillna(0, inplace=True)  # nan值和0都要去掉
        # 利用周期范围过滤一部分点
        # extreme_max_points_1500 = extreme_max_points_1500[(800 < T_R.values.flatten()) &
        #                                                   (T_R.values.flatten() < 2000)]
        extreme_max_points_1500 = extreme_max_points_1500[(800 < T_R.values.flatten())]
        # 利用赋值范围过滤一部分点
        pass

        extreme_max_points_1500 = extreme_max_points_1500[~np.isnan(extreme_max_points_1500).any(axis=1)]
        R = pd.DataFrame(extreme_max_points_1500[..., 1],
                         index=extreme_max_points_1500[..., 0].astype(np.int), columns=['R'])
        return R

    def get_QRS(self, extreme_points, R):
        """
        通过R点匹配QS点，若R点找不到匹配的QS点则去除
        :param extreme_points:
        :param R:
        :return:
        """
        extreme_points = extreme_points.reshape(-1, 2)
        extreme_points = extreme_points[~(extreme_points == 0.0).any(axis=1)]
        extreme_points = extreme_points[~np.isnan(extreme_points).any(axis=1)]
        QRS_index = np.apply_along_axis(self.get_adjacent_rows, 1,
                                        R.index.values.reshape(-1, 1),
                                        extreme_points[..., 0].astype(np.int).reshape(-1, 1))
        QRS_index = QRS_index[~(QRS_index == 0)]
        QRS = extreme_points[QRS_index]
        Q = pd.DataFrame(QRS[0::3, 1], index=QRS[0::3, 0].astype(np.int), columns=['Q'])
        R = pd.DataFrame(QRS[1::3, 1], index=QRS[1::3, 0].astype(np.int), columns=['R'])
        S = pd.DataFrame(QRS[2::3, 1], index=QRS[2::3, 0].astype(np.int), columns=['S'])
        return Q, R, S

    def get_T_R(self, R):
        """
        R需要是DataFrame类型，用到df的shift函数
        :param R:
        :return:
        """
        T = R - R.shift(1)
        T.columns = ['T_R']
        return T

    def get_T_QR(self, Q, R):
        Q = Q.reset_index(drop=True)
        R = R.reset_index(drop=True)
        # 只有一列自动转为Series
        T = (R[0] - Q[0]).to_frame()
        T.columns = ['T_QR']
        return T

    def get_T_RS(self, R, S):
        R = R.reset_index(drop=True)
        S = S.reset_index(drop=True)
        # 只有一列自动转为Series
        T = (S[0] - R[0]).to_frame()
        T.columns = ['T_RS']
        return T

    def extract_ecg_feats(self):

        # 提取全部极值点
        extreme_points = self.get_extreme_point(self.ecg_data)
        # 提取R点，目前存在周期性丢点问题
        R = self.get_R(self.ecg_data)
        Q, R, S = self.get_QRS(extreme_points, R)

        # 定要保证QRS对齐，否则周期计算无效
        T_R = self.get_T_R(pd.DataFrame(R.index))
        T_QR = self.get_T_QR(pd.DataFrame(Q.index), pd.DataFrame(R.index))
        T_RS = self.get_T_RS(pd.DataFrame(R.index), pd.DataFrame(S.index))

        Q_index = pd.DataFrame(Q.index, columns=['Q_index']).join(Q.reset_index(drop=True))
        R_index = pd.DataFrame(R.index, columns=['R_index']).join(R.reset_index(drop=True))
        S_index = pd.DataFrame(S.index, columns=['S_index']).join(S.reset_index(drop=True))
        feat_data = Q_index.join(R_index).join(S_index).join(
            T_R.reset_index(drop=True)).join(
            T_QR.reset_index(drop=True)).join(
            T_RS.reset_index(drop=True))

        # feat_data.index = R.index

        Q_mean = Q.mean().values
        R_mean = R.mean().values
        S_mean = S.mean().values
        T_R_mean = T_R.mean().values
        T_QR_mean = T_QR.mean().values
        T_RS_mean = T_RS.mean().values

        # 联合剔除异常数据
        feat_data = feat_data[~np.isnan(feat_data).any(axis=1)]
        feat_data = feat_data[(feat_data['R'].values > (R_mean / 2))]
        feat_data = feat_data[(feat_data['T_R'].values > (T_R_mean / 2))]
        feat_data = feat_data[(feat_data['T_QR'].values > (T_QR_mean / 2))]
        feat_data = feat_data[(feat_data['T_RS'].values > (T_RS_mean / 2))]
        feat_data = feat_data[(feat_data['T_QR'].values < 2 * T_QR_mean)]
        feat_data = feat_data[(feat_data['T_RS'].values < 2 * T_RS_mean)]

        feat_data = feat_data.reset_index(drop=True)
        feat_data.drop(['Q_index', 'R_index', 'S_index'], axis=1, inplace=True)

        # Z-score标准化
        feat_data = ((feat_data - feat_data.mean()) / (feat_data.std())).values

        return feat_data
