from django.shortcuts import render
import pandas as pd
import numpy as np
from django.http import HttpResponseRedirect, HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView

try:
    from io import BytesIO as IO # for modern python
except ImportError:
    from io import StringIO as IO # for legacy python


@method_decorator(login_required, name='dispatch')
class UserUpdateView(UpdateView):
    model = User
    fields = ('first_name', 'last_name', 'email', )
    template_name = 'my_account.html'
    success_url = reverse_lazy('my_account')

    def get_object(self):
        return self.request.user


def read_table(filename, enconding='iso8859'):
    df = pd.read_csv(filename, sep='\t', encoding=enconding, decimal=',')
    df.drop([0], axis=0, inplace=True)  ##se borra la fila 0
    time_index = pd.to_datetime(df['Fecha'] + ' ' + df['Intervalo inicial'], format='%d/%m/%Y %H:%M')
    # time_index=time_index.dt.strftime('%d-%m-%Y %H:%M') ##se formatea a este orden
    df.index = time_index  ##se asigna el indice usando la col 'Fecha' e 'Intervalo inicial' al formato YYYY-DD-MM HH:MM
    df.drop(['Fecha', 'Intervalo inicial'], axis=1, inplace=True)  ##se borra la columna fecha e intervalo inicial
    return df


def pandas_query(df, group):
    dfilt = False
    for project in group:
        dfilt = (df['PROYECTO'] == project) + dfilt
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
    table['Abandono'] = llamadas_ofrecidas - llamadas_atendidas
    table['%Abandono'] = ((llamadas_ofrecidas - llamadas_atendidas) * 100 / llamadas_ofrecidas).round(1)
    table['AHT'] = (sum_tiempo / llamadas_atendidas)
    table['ASA'] = llam_atend_x_vel_prom / llamadas_atendidas
    table['%Atención'] = llamadas_atendidas * 100 / llamadas_ofrecidas
    table['%Servicio'] = llamadas_umbral * 100 / llamadas_ofrecidas
    table['%Anterior'] = llamadas_umbral_anterior * 100 / llamadas_ofrecidas_anterior
    table['D'] = table['%Servicio'] - table['%Anterior']
    table['D'] = table['D'].map(lambda x: 'up' if x >= 0 else 'down')
    table['Total Abandonadas'] = table['Abandono']
    table['Abandonadas después de Umbral'] = abandonadas_despues_umbral
    table['%Nivel de abandono'] = abandonadas_despues_umbral * 100 / llamadas_ofrecidas
    table = table.round(1)
    table['%Abandono'] = table['%Abandono'].astype(str) + '%'
    table['%Atención'] = table['%Atención'].astype(str) + '%'
    table['%Servicio'] = table['%Servicio'].astype(str) + '%'
    table['%Anterior'] = table['%Anterior'].astype(str) + '%'
    table['%Nivel de abandono'] = table['%Nivel de abandono'].astype(str) + '%'
    return table


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

    df = read_table('repsep.txt')
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

    table_g1_str = table_g1.to_html(classes='format1').replace('up', '<i class="ni ni-bold-up up-color"></i>').replace(
        'down', '<i class="ni ni-bold-down down-color"></i>')
    table_g2_str = table_g2.to_html(classes='format2').replace('up', '<i class="ni ni-bold-up up-color"></i>').replace(
        'down', '<i class="ni ni-bold-down down-color"></i>')
    table_g3_str = table_g3.to_html(classes='format3').replace('up', '<i class="ni ni-bold-up up-color"></i>').replace(
        'down', '<i class="ni ni-bold-down down-color"></i>')
    tables = [table_g1_str, table_g2_str, table_g3_str]
    titles = ['SPPS n1', 'B2B Fibra', 'Verticales']

    return render(request, 'home.html',
                  dict(tables_dict=dict(zip(titles, tables)), start_hour=start_hour, start_minute=start_minute,
                       end_hour=end_hour, end_minute=end_minute, option1='false', option2='false', option3='false'))


def enviar2(request, table_id):
    print(table_id)
    return HttpResponseRedirect("/")

@login_required(login_url='/login/')
def enviar(request, table_id):
    grupo1 = ['B2B MDR Soporte', 'B2B MDR Edatel', 'B2B MDR Cierre']
    grupo2 = ['B2B Fibra']
    grupo3 = ['B2B N1 Bajos', 'B2B N1 Edatel Avanz', 'B2B N1 Edatel Basico', 'B2B N1 Medios Conect',
              'B2B N1 Medios Datace', 'B2B N1 Medios Voz', 'B2B N1 VIP']

    df = read_table('repsep.txt')
    print(table_id)
    if table_id == 1:
        excel_file = IO()
        xlwriter = pd.ExcelWriter(excel_file, engine='xlsxwriter')
        table_g1 = generate_table(df, grupo1, df.index[0], df.index[-1])
        table_g1.to_excel(xlwriter, 'SPPS_n1')
        xlwriter.save()
        xlwriter.close()
        excel_file.seek(0)
        response = HttpResponse(excel_file.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=Reporte_SPPS_n1.xlsx'
        return response

    if request.method == 'POST':
        date_start = request.POST['date_start']
        date_end = request.POST['date_end']
        start_hour = request.POST['start_hour']
        start_minute = request.POST['start_minute']
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

        print('date start:', date_start)
        print('date end:', date_end)
        print('start hour:', start_hour)
        print('start minute', start_minute)
        print('end hour:', end_hour)
        print('end minute:', end_minute)
        print('option1:', option1)
        print('option2:', option2)
        print('option3:', option3)


        # table_g3 = generate_table(df, grupo3, df.index[0], df.index[-1])
        # table_g3 = generate_table(df, grupo1, pd.to_datetime('2019-09-01'), pd.to_datetime('2019-09-01'))
        # dfg1 = df[pandas_query(grupo1)]
        # dfg2 = df[pandas_query(grupo2)]
        # dfg3 = df[pandas_query(grupo3)]

        tables = []
        titles = []

        if option1 == 'true':
            table_g1 = generate_table(df, grupo1, df.index[0], df.index[-1])
            table_str = table_g1.to_html(classes='format1').replace('up',
                                                                    '<i class="ni ni-bold-up up-color"></i>').replace(
                'down', '<i class="ni ni-bold-down down-color"></i>')
            tables.append(table_str)
            titles.append('SPPS n1')

        if option2 == 'true':
            table_g2 = generate_table(df, grupo2, df.index[0], df.index[-1])
            table_str = table_g2.to_html(classes='format2').replace('up',
                                                                    '<i class="ni ni-bold-up up-color"></i>').replace(
                'down', '<i class="ni ni-bold-down down-color"></i>')
            tables.append(table_str)
            titles.append('B2B Fibra')

        if option3 == 'true':
            table_g3 = generate_table(df, grupo3, df.index[0], df.index[-1])
            table_str = table_g3.to_html(classes='format3').replace('up',
                                                                   '<i class="ni ni-bold-up up-color"></i>').replace(
            'down', '<i class="ni ni-bold-down down-color"></i>')
            tables.append(table_str)
            titles.append('Verticales')

        # dfg1[dfg1['PROYECTO'] == grupo1[0]]['Llamadas Recibidas']['2019-09-01 00:00':'2019-09-03 00:15']
        # df['PROYECTO'][df.index <= (df.index[-1] - pd.Timedelta(minutes=15))]
        # df['PROYECTO'][df.index[0]:(df.index[-1] - pd.Timedelta(minutes=15))]

        return render(request, 'home.html',
                      dict(tables_dict=dict(zip(titles, tables)), start_hour=start_hour, start_minute=start_minute,
                          end_hour=end_hour, end_minute=end_minute, date_start=date_start, date_end=date_end,
                          option1=option1, option2=option2, option3=option3))

    else:
        return HttpResponseRedirect("/")
