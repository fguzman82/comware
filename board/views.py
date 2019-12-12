from django.shortcuts import render
import pandas as pd
import numpy as np
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

try:
    from io import BytesIO as IO  # for modern python
except ImportError:
    from io import StringIO as IO  # for legacy python


@method_decorator(login_required, name='dispatch')
class UserUpdateView(UpdateView):
    model = User
    fields = ('first_name', 'last_name', 'email',)
    template_name = 'my_account.html'
    success_url = reverse_lazy('my_account')

    def get_object(self):
        return self.request.user


def read_table(filename, enconding='iso8859'):
    df = pd.read_csv(filename, sep='\t', encoding=enconding, decimal='.')
    df.drop([0], axis=0, inplace=True)  ##se borra la fila 0
    time_index = pd.to_datetime(df['Fecha'] + ' ' + df['Intervalo inicial'], format='%m/%d/%Y %I:%M %p')
    # time_index=time_index.dt.strftime('%d-%m-%Y %H:%M') ##se formatea a este orden
    df.index = time_index  ##se asigna el indice usando la col 'Fecha' e 'Intervalo inicial' al formato YYYY-DD-MM HH:MM
    df.drop(['Fecha', 'Intervalo inicial'], axis=1, inplace=True)  ##se borra la columna fecha e intervalo inicial
    return df


def pandas_query(df, group):
    dfilt = False
    for project in group:
        dfilt = (df['PROYECTO'] == project) | dfilt
    return dfilt


def pd_index_range(dataframe):
    init_year = dataframe.index.year[0]
    init_month = dataframe.index.month[0]
    init_day = dataframe.index.day[0]
    init_hour = dataframe.index.hour[0]
    init_min = dataframe.index.minute[0]
    end_year = dataframe.index.year[-1]
    end_month = dataframe.index.month[-1]
    end_day = dataframe.index.day[-1]
    end_hour = dataframe.index.hour[-1]
    end_min = dataframe.index.minute[-1]
    init_date = str(init_year) + '-' + str(init_month) + '-' + str(init_day) + ' ' + str(init_hour) + ':' + str(
        init_min)
    end_date = str(end_year) + '-' + str(end_month) + '-' + str(end_day) + ' ' + str(end_hour) + ':' + str(end_min)
    return init_date, end_date


def generate_table(df, group, time_start, time_end):
    llamadas_ofrecidas = np.array(
        [(df[df['PROYECTO'] == project]['Llamadas Recibidas'][time_start:time_end].sum()) for project in group])
    llamadas_ofrecidas_anterior = np.array(
        [(df[df['PROYECTO'] == project]['Llamadas Recibidas'][time_start:time_end - pd.Timedelta(minutes=15)].sum()) for
         project in group])
    llamadas_atendidas = np.array(
        [(df[df['PROYECTO'] == project]['Llamadas Atendidas'][time_start:time_end].sum()) for project in group])
    llamadas_umbral = np.array(
        [(df[df['PROYECTO'] == project]['LLamadas Umbral'][time_start:time_end].sum()) for project in group])
    llamadas_umbral_anterior = np.array(
        [(df[df['PROYECTO'] == project]['LLamadas Umbral'][time_start:time_end - pd.Timedelta(minutes=15)].sum()) for
         project in group])
    sum_tiempo = np.array(
        [(df[df['PROYECTO'] == project][['Tiempo ACD', 'ACWINTIME', 'Tiempo de reten.']][time_start:time_end].sum()) for
         project in group]).sum(axis=1)
    llam_atend_x_vel_prom = np.array([(((df[df['PROYECTO'] == project]['Llamadas Atendidas'][time_start:time_end]) * (
        df[df['PROYECTO'] == project]['Vel. prom. de resp.'][time_start:time_end])).sum()) for project in group])

    abandonadas_despues_umbral = np.array(
        [(df[df['PROYECTO'] == project][['Aban Calls 21 - 30 sec.', 'Aban Calls 31 -60 sec.', 'Aban Calls > 60 sec.']][
          time_start:time_end].sum()) for project in group]).sum(axis=1)

    table = pd.DataFrame(index=group)
    table['Ofrecidas'] = llamadas_ofrecidas
    table['Atendidas'] = llamadas_atendidas
    table['Umbral'] = llamadas_umbral
    #table['Abandono'] = llamadas_ofrecidas - llamadas_atendidas
    table['%Abandono'] = ((llamadas_ofrecidas - llamadas_atendidas) * 100 / llamadas_ofrecidas).round(1)
    table['AHT'] = (sum_tiempo / llamadas_atendidas)
    table['ASA'] = llam_atend_x_vel_prom / llamadas_atendidas
    table['%Atención'] = llamadas_atendidas * 100 / llamadas_ofrecidas
    table['%Servicio'] = llamadas_umbral * 100 / llamadas_ofrecidas
    #table['%Anterior'] = llamadas_umbral_anterior * 100 / llamadas_ofrecidas_anterior
    #table['D'] = table['%Servicio'] - table['%Anterior']
    #table['D'] = table['D'].map(lambda x: 'up' if x >= 0 else 'down')
    table['Total Abandonadas'] = llamadas_ofrecidas - llamadas_atendidas
    table['Abandonadas después de Umbral'] = abandonadas_despues_umbral
    table['%Nivel de abandono'] = abandonadas_despues_umbral * 100 / llamadas_ofrecidas

    table.loc['TOTAL', 'Ofrecidas'] = llamadas_ofrecidas.sum()
    table.loc['TOTAL', 'Atendidas'] = llamadas_atendidas.sum()
    table.loc['TOTAL', 'Umbral'] = llamadas_umbral.sum()
    total_abandono = (llamadas_ofrecidas - llamadas_atendidas).sum()
    table.loc['TOTAL', '%Abandono'] = total_abandono * 100 / table.loc['TOTAL', 'Ofrecidas']
    table.loc['TOTAL', 'AHT'] = sum_tiempo.sum() / table.loc['TOTAL', 'Atendidas']
    table.loc['TOTAL', 'ASA'] = llam_atend_x_vel_prom.sum() / table.loc['TOTAL', 'Atendidas']
    table.loc['TOTAL', '%Atención'] = table.loc['TOTAL', 'Atendidas'] * 100 / table.loc['TOTAL', 'Ofrecidas']
    table.loc['TOTAL', '%Servicio'] = table.loc['TOTAL', 'Umbral'] * 100 / table.loc['TOTAL', 'Ofrecidas']
    #table.loc['TOTAL', '%Anterior'] = llamadas_umbral_anterior.sum() * 100 / llamadas_ofrecidas_anterior.sum()
    #table.loc['TOTAL', 'D'] = table.loc['TOTAL', '%Servicio'] - table.loc['TOTAL', '%Anterior']
    #table.loc['TOTAL', 'D'] = 'up' if table.loc['TOTAL', 'D'] >= 0 else 'down'
    table.loc['TOTAL', 'Total Abandonadas'] = total_abandono
    table.loc['TOTAL', 'Abandonadas después de Umbral'] = abandonadas_despues_umbral.sum()
    table.loc['TOTAL', '%Nivel de abandono'] = table.loc['TOTAL', 'Abandonadas después de Umbral'] * 100 / table.loc[
        'TOTAL', 'Ofrecidas']

    table = table.round(1)
    table['%Abandono'] = table['%Abandono'].astype(str) + '%'
    table['%Atención'] = table['%Atención'].astype(str) + '%'
    table['%Servicio'] = table['%Servicio'].astype(str) + '%'
    #table['%Anterior'] = table['%Anterior'].astype(str) + '%'
    table['%Nivel de abandono'] = table['%Nivel de abandono'].astype(str) + '%'

    table = table.reindex(['TOTAL'] + group)

    return table


def generate_dashboard(df, NS_hora, NA_hora, NS_gauge, NA_gauge, AHT, AHT_str, table_g):
    fig = make_subplots(
        rows=2, cols=4,
        vertical_spacing=0.02, #separacion entre filas
        #horizontal_spacing=0.15,  #separacion entre columnas
        column_widths=[0.2, 0.2, 0.09, 0.51],
        row_heights=[0.19, 0.81],

        subplot_titles=[None, None, None, "Número de llamadas", None, None],

        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}, {"type": "xy"}],
               [{"type": "xy", "colspan": 4, "secondary_y": True, "t": 0.025}, None, None, None]]
               #[{"type": "table", "colspan": 4}, None, None, None]]
    )

    fig.add_trace(
        go.Indicator(
        mode="gauge+number",
        value=NS_gauge,
        #delta = {'reference': serv_ant_delta},
        #domain={'row': 1, 'column': 1},
        title={'text': "Nivel de Servicio", 'font':{'size': 17} },
        number={'suffix': '%', 'font':{'color': '#0a650a'}},
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "#0a650a"},
            'bgcolor': "lightgray",
            'borderwidth': 2,
            'bordercolor': "gray",
            'threshold': {
                'line': {'color': "#8b0000", 'width': 4},
                'thickness': 0.75,
                'value': NS_gauge}}
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Indicator(
        mode="gauge+number",
        value=NA_gauge,
        #domain={'row': 1, 'column': 2},
        title={'text': "Nivel de Atención", 'font':{'size': 17} },
        number={'suffix': '%', 'font':{'color': '#195695'}},
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "#195695"},
            'bgcolor': "lightgray",
            'borderwidth': 2,
            'bordercolor': "gray",
            'threshold': {
                'line': {'color': "#8b0000", 'width': 4},
                'thickness': 0.75,
                'value': NA_gauge}}
        ),
        row=1, col=2
    )

    fig.add_trace(go.Indicator(
        mode = "number",
        value = AHT,
        number={'suffix': ' seg'},
        title = {"text": "AHT<br><span style='font-size:0.8em;color:gray'>"+ AHT_str +"s</span>"},
        #delta = {'reference': 400, 'relative': True}
        ),
        row=1, col=3
    )

    fig.add_trace(
        go.Waterfall(
        name="Acumulado",
        orientation="h",
        measure=['absolute', 'relative', 'absolute', 'absolute'],
        y=['ofrecidas', 'abandonadas', 'atendidas', 'umbral'],
        x=[table_g['Ofrecidas']['TOTAL'], -table_g['Total Abandonadas']['TOTAL'], table_g['Atendidas']['TOTAL'],
           table_g['Umbral']['TOTAL']],
        decreasing={"marker": {"color": "darkslategray", "line": {"color": "darkslategrey", "width": 1}}},
        totals={"marker": {"color": "#195695", "line": {"color": "#195695", "width": 1}}},
        textposition="inside",
        text=[str(table_g['Ofrecidas']['TOTAL']), str(table_g['Total Abandonadas']['TOTAL']), str(table_g['Atendidas']['TOTAL']),
              str(table_g['Umbral']['TOTAL'])],
        textfont={'size': 15},
        xaxis='x',
        yaxis='y',
        # connector = {"mode":"between", "line":{"width":4, "color":"rgb(0, 0, 0)", "dash":"solid"}}
        ),
        row=1, col=4
    )

    indice=df['LLamadas Umbral'].resample('1h').sum().index
    llamadas_umbral=df['LLamadas Umbral'].resample('1h').sum().values
    llamadas_atendidas=df['Llamadas Atendidas'].resample('1h').sum().values
    llamadas_recibidas=df['Llamadas Recibidas'].resample('1h').sum().values

    fig.add_trace(
        go.Bar(
            x=indice,
            y=llamadas_umbral,
            text=llamadas_umbral,
            textposition='inside',
            name='Dentro de Umbral',
            marker_color='rgb(26, 118, 255)',
            xaxis="x2",
            yaxis="y2",
        ),
        row=2, col=1, secondary_y=False
    )

    fig.add_trace(
        go.Bar(
            x=indice,
            y=llamadas_atendidas - llamadas_umbral,
            text=llamadas_atendidas - llamadas_umbral,
            textposition='inside',
            name='Después de Umbral',
            marker_color='rgb(55, 83, 109)',
            xaxis="x2",
            yaxis="y2",
        ),
        row=2, col=1, secondary_y=False
    )

    fig.add_trace(
        go.Bar(
            x=indice,
            y=llamadas_recibidas - llamadas_atendidas,
            text=llamadas_recibidas - llamadas_atendidas,
            textposition='inside',
            name='Abandonadas',
            marker_color='lightgrey',
            xaxis="x2",
            yaxis="y2",
        ),
        row=2, col=1, secondary_y=False
    )

    fig.add_trace(
        go.Scatter(
            mode='markers+text',
            x=indice,
            y=llamadas_recibidas,
            text=llamadas_recibidas,
            textposition='top center',
            name='Recibidas',
            # marker_color='blue',
            marker=dict(
                color='Blue',
                size=10,
            ),
            xaxis="x2",
            yaxis="y2",
        ),
        row=2, col=1, secondary_y=False
    )

    fig.add_trace(
        go.Scatter(
            mode='lines+markers+text',
            x=indice,
            y=NS_hora.interpolate(how='linear').values,
            #text=[s+'%' for s in list(map(str,NS_hora.interpolate(how='linear').values.round(1).tolist()))],
            hovertemplate = 'Nivel de servicio'+' %{x}'+'<br>%{y:.2f} % <extra></extra></br>',
            #textposition='top center',
            name='Nivel de Servicio (%)',
            marker_color='green',
            xaxis="x2",
            yaxis="y3",
            line=dict(width=4,
                      shape='spline',
                      smoothing=1
                      ),
        ),
        row=2, col=1, secondary_y=True
    )

    fig.add_trace(
        go.Scatter(
            mode='lines+markers+text',
            x=indice,
            y=NA_hora.interpolate(how='linear').values,
            #text=[s+'%' for s in list(map(str,NA_hora.interpolate(how='linear').values.round(1).tolist()))],
            hovertemplate = 'Nivel de Atención'+' %{x}'+'<br>%{y:.2f} % <extra></extra></br>',
            #textposition='bottom center',
            name='Nivel de Atención (%)',
            marker_color='#195695',
            xaxis="x2",
            yaxis="y3",
            line=dict(width=4,
                      shape='spline',
                      smoothing=1
                      ),
        ),
        row=2, col=1, secondary_y=True
    )

    fig.update_layout(
        height=650,
        width=1100,
        autosize=False,
        dragmode=False,
        template='plotly', #seaborn #ggplot2

        xaxis=dict(anchor="y"),
        xaxis2=dict(tickfont_size=12, dtick=3600000, tickformat='%I:%M %p', anchor="y2", tickangle=25),

        yaxis=dict(anchor="x"),
        yaxis2=dict(
            title='Número de llamadas',
            titlefont_size=16,
            tickfont_size=14,
            side="left",
            anchor="x2"
        ),
        yaxis3=dict(
            title='Porcentaje',
            range=[0, 110],
            ticksuffix='%',
            titlefont_size=16,
            tickfont_size=14,
            side="right",
            showgrid=False,
            overlaying="y2",
            anchor="x2",

        ),

        legend=dict(
            x=0.01,
            y=0.5,
            bgcolor='rgba(128, 100, 0, 0)',
            bordercolor='rgba(255, 255, 255, 0)'
        ),
        barmode='stack',
        bargap=0.15,  # gap between bars of adjacent location coordinates.
        bargroupgap=0.31,  # gap between bars of the same location coordinate.

    )

    return fig.to_html(full_html=False, include_plotlyjs=False)

# df_B2B_Fibra=df[df.PROYECTO=='B2B Fibra']
# print(df_B2B_Fibra.loc['2019-Sept 00:00':'2019-Sept 01:45'])
# print(df_B2B_Fibra.loc['2019-Sept 00:00':'2019-Sept 01:45','Tiempo dispon.'])


# Create your views here._g1
@login_required(login_url='/login/')
def home(request):
    grupo1 = ['B2B MDR Soporte', 'B2B MDR Edatel', 'B2B MDR Cierre']
    grupo2 = ['B2B Fibra']
    grupo3 = ['B2B N1 Bajos', 'B2B N1 Edatel Avanz', 'B2B N1 Edatel Basico', 'B2B N1 Medios Conect',
              'B2B N1 Medios Datace', 'B2B N1 Medios Voz', 'B2B N1 VIP']

    df = read_table('tabla.txt')
    global end_date
    end_date = df.index[-1]

    current_date_year = timezone.now().date().year
    current_date_month = timezone.now().date().month
    current_date_day = timezone.now().date().day
    current_date = str(current_date_day) + '/' + str(current_date_month) + '/' + str(current_date_year)
    start_hour = 'Hora inicio'
    start_minute = 'Minuto inicio'
    end_hour = 'Hora Final'
    end_minute = 'Minuto Final'
    print('current date is:', (current_date))

    table_g1 = generate_table(df, grupo1, df.index[0], df.index[-1])
    table_g2 = generate_table(df, grupo2, df.index[0], df.index[-1])
    table_g3 = generate_table(df, grupo3, df.index[0], df.index[-1])

    date_cutting = (df.index[-1] + pd.Timedelta(minutes=15))
    date_cutting = date_cutting.strftime("%e %b &nbsp %I:%M %p")

    tabla_stts_str = table_g1.to_html(classes='format1" id="tabla_stts')
    tabla_fibra_str = table_g2.to_html(classes='format1" id="tabla_fibra')
    tabla_verticales_str = table_g3.to_html(classes='format1" id="tabla_verticales')

    # tables = [table_g1_str, table_g2_str, table_g3_str]
    # titles = ['B2B Fibra', 'STTS n1', 'Verticales']

    servicio_stts = table_g1['%Servicio']['TOTAL']
    atencion_stts = table_g1['%Atención']['TOTAL']
    AHT_stts = table_g1['AHT']['TOTAL']
    AHT_stts_str = str(datetime.timedelta(seconds=int(AHT_stts)))
    NS_gauge_stts = float(servicio_stts[0:-1])
    NA_gauge_stts = float(atencion_stts[0:-1])

    servicio_fibra = table_g2['%Servicio']['TOTAL']
    atencion_fibra = table_g2['%Atención']['TOTAL']
    AHT_fibra = table_g2['AHT']['TOTAL']
    AHT_fibra_str = str(datetime.timedelta(seconds=int(AHT_fibra)))
    NS_gauge_fibra = float(servicio_fibra[0:-1])
    NA_gauge_fibra = float(atencion_fibra[0:-1])

    servicio_verticales = table_g3['%Servicio']['TOTAL']
    atencion_verticales = table_g3['%Atención']['TOTAL']
    AHT_verticales = table_g3['AHT']['TOTAL']
    AHT_verticales_str = str(datetime.timedelta(seconds=int(AHT_verticales)))
    NS_gauge_verticales = float(servicio_verticales[0:-1])
    NA_gauge_verticales = float(atencion_verticales[0:-1])

    df1 = df[pandas_query(df, grupo1)]
    df2 = df[pandas_query(df, grupo2)]
    df3 = df[pandas_query(df, grupo3)]

    NS_stts_hora = df1['Llamadas Atendidas'].resample('1h').sum() * 100 / df1['Llamadas Recibidas'].resample('1h').sum()
    NA_stts_hora = df1['LLamadas Umbral'].resample('1h').sum() * 100 / df1['Llamadas Recibidas'].resample('1h').sum()

    NS_fibra_hora = df2['Llamadas Atendidas'].resample('1h').sum() * 100 / df2['Llamadas Recibidas'].resample('1h').sum()
    NA_fibra_hora = df2['LLamadas Umbral'].resample('1h').sum() * 100 / df2['Llamadas Recibidas'].resample('1h').sum()

    NS_verticales_hora = df3['Llamadas Atendidas'].resample('1h').sum() * 100 / df3['Llamadas Recibidas'].resample('1h').sum()
    NA_verticales_hora = df3['LLamadas Umbral'].resample('1h').sum() * 100 / df3['Llamadas Recibidas'].resample('1h').sum()

    verticales_dashboard = generate_dashboard(df3, NS_verticales_hora, NA_verticales_hora, NS_gauge_verticales,
                                    NA_gauge_verticales, AHT_verticales, AHT_verticales_str, table_g3)

    sttsn1_dashboard = generate_dashboard(df1, NS_stts_hora, NA_stts_hora, NS_gauge_stts,
                                    NA_gauge_stts, AHT_stts, AHT_stts_str, table_g1)

    fibra_dashboard = generate_dashboard(df2, NS_fibra_hora, NA_fibra_hora, NS_gauge_fibra,
                                          NA_gauge_fibra, AHT_fibra, AHT_fibra_str, table_g2)

    fig = make_subplots(
        rows=3, cols=4,
        vertical_spacing=0.2,  # separacion entre filas
        horizontal_spacing=0.07,  # separacion entre columnas
        column_widths=[0.2, 0.2, 0.09, 0.51],
        row_heights=[0.34, 0.33, 0.33],

        # row_titles=["row1", "row2", "row3"],
        # y_title="Verticales",
        # subplot_titles=[None, None, None, "Número de llamadas", None, None, None, "Número de llamadas", None, None, None, "Número de llamadas"],

        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}, {"type": "xy", "l": 0.025}],
               [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}, {"type": "xy", "l": 0.025}],
               [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}, {"type": "xy", "l": 0.025}]]
    )

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=NS_gauge_verticales,
            # delta = {'reference': serv_ant_delta},
            # domain={'row': 1, 'column': 1},
            title={'text': "Nivel de Servicio", 'font': {'size': 16}},
            number={'suffix': '%', 'font': {'color': '#0a650a'}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue", 'visible': False},
                'bar': {'color': "#0a650a"},
                'bgcolor': "lightgray",
                'borderwidth': 2,
                'bordercolor': "gray",
                'threshold': {
                    'line': {'color': "#8b0000", 'width': 4},
                    'thickness': 0.75,
                    'value': NS_gauge_verticales}}
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=NA_gauge_verticales,
            # domain={'row': 1, 'column': 2},
            title={'text': "Nivel de Atención", 'font': {'size': 16}},
            number={'suffix': '%', 'font': {'color': '#195695'}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue", 'visible': False},
                'bar': {'color': "#195695"},
                'bgcolor': "lightgray",
                'borderwidth': 2,
                'bordercolor': "gray",
                'threshold': {
                    'line': {'color': "#8b0000", 'width': 4},
                    'thickness': 0.75,
                    'value': NA_gauge_verticales}}
        ),
        row=1, col=2
    )

    fig.add_trace(go.Indicator(
        mode="number",
        value=AHT_verticales,
        number={'suffix': ' seg'},
        title={"text": "AHT<br><span style='font-size:0.8em;color:gray'>" + AHT_verticales_str + "s</span>",
               'font': {'size': 18}},
        # delta = {'reference': 400, 'relative': True}
    ),
        row=1, col=3
    )

    fig.add_trace(
        go.Waterfall(
            name="Acumulado",
            orientation="h",
            measure=['absolute', 'relative', 'absolute', 'absolute'],
            y=['ofrecidas', 'abandonadas', 'atendidas', 'umbral'],
            x=[table_g3['Ofrecidas']['TOTAL'], -table_g3['Total Abandonadas']['TOTAL'], table_g3['Atendidas']['TOTAL'],
               table_g3['Umbral']['TOTAL']],
            decreasing={"marker": {"color": "darkslategray", "line": {"color": "darkslategrey", "width": 1}}},
            totals={"marker": {"color": "#195695", "line": {"color": "#195695", "width": 1}}},
            textposition="inside",
            text=[str(table_g3['Ofrecidas']['TOTAL']), str(table_g3['Total Abandonadas']['TOTAL']),
                  str(table_g3['Atendidas']['TOTAL']),
                  str(table_g3['Umbral']['TOTAL'])],
            textfont={'size': 15},
            xaxis='x',
            yaxis='y',
            # connector = {"mode":"between", "line":{"width":4, "color":"rgb(0, 0, 0)", "dash":"solid"}}
        ),
        row=1, col=4
    )

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=NS_gauge_stts,
            # delta = {'reference': serv_ant_delta},
            # domain={'row': 1, 'column': 1},
            title={'text': "Nivel de Servicio", 'font': {'size': 16}},
            number={'suffix': '%', 'font': {'color': '#0a650a'}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue", 'visible': False},
                'bar': {'color': "#0a650a"},
                'bgcolor': "lightgray",
                'borderwidth': 2,
                'bordercolor': "gray",
                'threshold': {
                    'line': {'color': "#8b0000", 'width': 4},
                    'thickness': 0.75,
                    'value': NS_gauge_stts}}
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=NA_gauge_stts,
            # domain={'row': 1, 'column': 2},
            title={'text': "Nivel de Atención", 'font': {'size': 16}},
            number={'suffix': '%', 'font': {'color': '#195695'}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue", 'visible': False},
                'bar': {'color': "#195695"},
                'bgcolor': "lightgray",
                'borderwidth': 2,
                'bordercolor': "gray",
                'threshold': {
                    'line': {'color': "#8b0000", 'width': 4},
                    'thickness': 0.75,
                    'value': NA_gauge_stts}}
        ),
        row=2, col=2
    )

    fig.add_trace(go.Indicator(
        mode="number",
        value=AHT_stts,
        number={'suffix': ' seg'},
        title={"text": "AHT<br><span style='font-size:0.8em;color:gray'>" + AHT_stts_str + "s</span>",
               'font': {'size': 18}},
        # delta = {'reference': 400, 'relative': True}
    ),
        row=2, col=3
    )

    fig.add_trace(
        go.Waterfall(
            name="Acumulado",
            orientation="h",
            measure=['absolute', 'relative', 'absolute', 'absolute'],
            y=['ofrecidas', 'abandonadas', 'atendidas', 'umbral'],
            x=[table_g1['Ofrecidas']['TOTAL'], -table_g1['Total Abandonadas']['TOTAL'], table_g1['Atendidas']['TOTAL'],
               table_g1['Umbral']['TOTAL']],
            decreasing={"marker": {"color": "darkslategray", "line": {"color": "darkslategrey", "width": 1}}},
            totals={"marker": {"color": "#195695", "line": {"color": "#195695", "width": 1}}},
            textposition="inside",
            text=[str(table_g1['Ofrecidas']['TOTAL']), str(table_g1['Total Abandonadas']['TOTAL']),
                  str(table_g1['Atendidas']['TOTAL']),
                  str(table_g1['Umbral']['TOTAL'])],
            textfont={'size': 15},
            xaxis='x',
            yaxis='y',
            # connector = {"mode":"between", "line":{"width":4, "color":"rgb(0, 0, 0)", "dash":"solid"}}
        ),
        row=2, col=4
    )

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=NS_gauge_fibra,
            # delta = {'reference': serv_ant_delta},
            # domain={'row': 1, 'column': 1},
            title={'text': "Nivel de Servicio", 'font': {'size': 16}},
            number={'suffix': '%', 'font': {'color': '#0a650a'}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue", 'visible': False},
                'bar': {'color': "#0a650a"},
                'bgcolor': "lightgray",
                'borderwidth': 2,
                'bordercolor': "gray",
                'threshold': {
                    'line': {'color': "#8b0000", 'width': 4},
                    'thickness': 0.75,
                    'value': NS_gauge_fibra}}
        ),
        row=3, col=1
    )

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=NA_gauge_fibra,
            # domain={'row': 1, 'column': 2},
            title={'text': "Nivel de Atención", 'font': {'size': 16}},
            number={'suffix': '%', 'font': {'color': '#195695'}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue", 'visible': False},
                'bar': {'color': "#195695"},
                'bgcolor': "lightgray",
                'borderwidth': 2,
                'bordercolor': "gray",
                'threshold': {
                    'line': {'color': "#8b0000", 'width': 4},
                    'thickness': 0.75,
                    'value': NA_gauge_fibra}}
        ),
        row=3, col=2
    )

    fig.add_trace(go.Indicator(
        mode="number",
        value=AHT_fibra,
        number={'suffix': ' seg'},
        title={"text": "AHT<br><span style='font-size:0.8em;color:gray'>" + AHT_fibra_str + "s</span>",
               'font': {'size': 18}},
        # delta = {'reference': 400, 'relative': True}
    ),
        row=3, col=3
    )

    fig.add_trace(
        go.Waterfall(
            name="Acumulado",
            orientation="h",
            measure=['absolute', 'relative', 'absolute', 'absolute'],
            y=['ofrecidas', 'abandonadas', 'atendidas', 'umbral'],
            x=[table_g2['Ofrecidas']['TOTAL'], -table_g2['Total Abandonadas']['TOTAL'], table_g2['Atendidas']['TOTAL'],
               table_g2['Umbral']['TOTAL']],
            decreasing={"marker": {"color": "darkslategray", "line": {"color": "darkslategrey", "width": 1}}},
            totals={"marker": {"color": "#195695", "line": {"color": "#195695", "width": 1}}},
            textposition="inside",
            text=[str(table_g2['Ofrecidas']['TOTAL']), str(table_g2['Total Abandonadas']['TOTAL']),
                  str(table_g2['Atendidas']['TOTAL']),
                  str(table_g2['Umbral']['TOTAL'])],
            textfont={'size': 15},
            xaxis='x',
            yaxis='y',
            # connector = {"mode":"between", "line":{"width":4, "color":"rgb(0, 0, 0)", "dash":"solid"}}
        ),
        row=3, col=4
    )

    fig.update_layout(
        height=710,
        width=1100,
        template='plotly',  # seaborn #ggplot2
        showlegend=False,
        # paper_bgcolor="#f8f9fe",
        # plot_bgcolor="#f8f9fe",
        # autosize=True,
        dragmode=False,
        # title={'text':'Operación del dia (hora por hora)',
        #         'y':0.98,
        #         'x':0.5,
        #        'xanchor': 'center',
        #        'yanchor': 'top'
        #         },
        shapes=[go.layout.Shape(
            fillcolor="rgba(76, 175, 80, 0.1)",
            line={"width": 0},
            type="rect",
            x0=-0.09,
            x1=1.09,
            xref="paper",
            y0=0.29,
            y1=0.705,
            yref="paper",
            layer="below"
        )
        ],

        # margin=go.layout.Margin(
        #         #l=50,
        #         r=0,
        #         b=60,
        #         t=60
        #     ),
        annotations=[
            go.layout.Annotation(
                x=-0.05,
                y=1,
                showarrow=False,
                text="<b>Verticales</b>",
                font={'size': 16},
                textangle=-90,
                xref="paper",
                yref="paper"
            ),
            go.layout.Annotation(
                x=-0.05,
                y=0.5,
                showarrow=False,
                text="<b>STTS n1</b>",
                font={'size': 16},
                textangle=-90,
                xref="paper",
                yref="paper"
            ),
            go.layout.Annotation(
                x=-0.05,
                y=0.02,
                showarrow=False,
                text="<b>Fibra</b>",
                font={'size': 16},
                textangle=-90,
                xref="paper",
                yref="paper"
            )
        ],

    )

    resumen = fig.to_html(full_html=False, include_plotlyjs=False)

    if request.is_ajax():
        print('hola ajax')
        return JsonResponse(dict(zip(titles, tables)))
    else:
        print('hola reload')
        return render(request, 'home.html',
                      dict(resumen=resumen,
                           verticales_dashboard=verticales_dashboard, tabla_verticales=tabla_verticales_str,
                           sttsn1_dashboard=sttsn1_dashboard, tabla_sttsn1=tabla_stts_str,
                           fibra_dashboard=fibra_dashboard, tabla_fibra=tabla_fibra_str, date_cutting=date_cutting))


def enviar2(request, table_id):
    print(table_id)
    return HttpResponseRedirect("/")


@login_required(login_url='/login/')
def enviar(request, table_id):
    grupo1 = ['B2B MDR Soporte', 'B2B MDR Edatel', 'B2B MDR Cierre']
    grupo2 = ['B2B Fibra']
    grupo3 = ['B2B N1 Bajos', 'B2B N1 Edatel Avanz', 'B2B N1 Edatel Basico', 'B2B N1 Medios Conect',
              'B2B N1 Medios Datace', 'B2B N1 Medios Voz', 'B2B N1 VIP']

    df = read_table('tabla.txt')
    global end_date

    if request.method == 'POST':
        # date_start = request.POST['date_start']
        # date_end = request.POST['date_end']
        # start_hour = request.POST['start_hour']
        # start_minute = request.POST['start_minute']
        end_hour = request.POST['end_hour']
        end_minute = request.POST['end_minute']

        try:
            option1 = request.POST['option1']
        except:
            option1 = 'false'

        try:
            option2 = request.POST['option2']
        except:
            option2 = 'false'

        try:
            option3 = request.POST['option3']
        except:
            option3 = 'false'

        # print('date start:', date_start)
        # print('date end:', date_end)
        # print('start hour:', start_hour)
        # print('start minute', start_minute)
        print('end hour:', end_hour)
        print('end minute:', end_minute)
        # print('option1:', option1)
        # print('option2:', option2)
        # print('option3:', option3)

        if end_hour == 'Hora Final' or end_minute == 'Minuto Final':
            end_date = df.index[-1]
        else:
            end_date = pd.to_datetime(df.index[0].date().__str__() + ' ' + str(end_hour) + ':' + str(end_minute))
            end_date = end_date - pd.Timedelta(minutes=15)
        if end_date > df.index[-1]:
            end_date = df.index[-1]

        date_cutting = (end_date + pd.Timedelta(minutes=15)).__str__()
        end_hour = (end_date + pd.Timedelta(minutes=15)).time().hour
        end_minute = (end_date + pd.Timedelta(minutes=15)).time().minute
        # table_g3 = generate_table(df, grupo3, df.index[0], df.index[-1])
        # table_g3 = generate_table(df, grupo1, pd.to_datetime('2019-09-01'), pd.to_datetime('2019-09-01'))
        # dfg1 = df[pandas_query(grupo1)]
        # dfg2 = df[pandas_query(grupo2)]
        # dfg3 = df[pandas_query(grupo3)]

        tables = []
        titles = []

        if option1 == 'true':
            table_g1 = generate_table(df, grupo1, df.index[0], end_date)
            table_str = table_g1.to_html(classes='format1" id="tabla1').replace('up',
                                                                    '<i class="ni ni-bold-up up-color"></i>').replace(
                'down', '<i class="ni ni-bold-down down-color"></i>')
            tables.append(table_str)
            titles.append('STTS n1')

        if option2 == 'true':
            table_g2 = generate_table(df, grupo2, df.index[0], end_date)
            table_str = table_g2.to_html(classes='format2" id="tabla2').replace('up',
                                                                    '<i class="ni ni-bold-up up-color"></i>').replace(
                'down', '<i class="ni ni-bold-down down-color"></i>')
            tables.append(table_str)
            titles.append('B2B Fibra')

        if option3 == 'true':
            table_g3 = generate_table(df, grupo3, df.index[0], end_date)
            table_str = table_g3.to_html(classes='format3" id="tabla3').replace('up',
                                                                    '<i class="ni ni-bold-up up-color"></i>').replace(
                'down', '<i class="ni ni-bold-down down-color"></i>')
            tables.append(table_str)
            titles.append('Verticales')

        # dfg1[dfg1['PROYECTO'] == grupo1[0]]['Llamadas Recibidas']['2019-09-01 00:00':'2019-09-03 00:15']
        # df['PROYECTO'][df.index <= (df.index[-1] - pd.Timedelta(minutes=15))]
        # df['PROYECTO'][df.index[0]:(df.index[-1] - pd.Timedelta(minutes=15))]

        return render(request, 'home.html',
                      dict(tables_dict=dict(zip(titles, tables)), end_hour=end_hour, end_minute=end_minute,
                           option1=option1, option2=option2, option3=option3, date_cutting=date_cutting))

    else:

        print(table_id)
        if table_id == 'STTS n1':
            excel_file = IO()
            xlwriter = pd.ExcelWriter(excel_file, engine='xlsxwriter')
            table_g1 = generate_table(df, grupo1, df.index[0], end_date)
            table_g1.to_excel(xlwriter, 'STTS_n1')
            xlwriter.save()
            xlwriter.close()
            excel_file.seek(0)
            response = HttpResponse(excel_file.read(),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=Reporte_STTS_n1.xlsx'
            return response

        if table_id == 'B2B Fibra':
            excel_file = IO()
            xlwriter = pd.ExcelWriter(excel_file, engine='xlsxwriter')
            table_g2 = generate_table(df, grupo2, df.index[0], end_date)
            table_g2.to_excel(xlwriter, 'B2B_Fibra')
            xlwriter.save()
            xlwriter.close()
            excel_file.seek(0)
            response = HttpResponse(excel_file.read(),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=Reporte_B2B_Fibra.xlsx'
            return response

        if table_id == 'Verticales':
            excel_file = IO()
            xlwriter = pd.ExcelWriter(excel_file, engine='xlsxwriter')
            table_g3 = generate_table(df, grupo3, df.index[0], end_date)
            table_g3.to_excel(xlwriter, 'Verticales')
            xlwriter.save()
            xlwriter.close()
            excel_file.seek(0)
            response = HttpResponse(excel_file.read(),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=Verticales.xlsx'
            return response

        return HttpResponseRedirect("/")

@login_required(login_url='/login/')
def answer_me(request):
    field = request.GET.get('inputValue')
    answer = 'You typed: ' + field

    data = {
        'respond': answer
    }
    return JsonResponse(data)
