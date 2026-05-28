using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;


namespace Bondicom_api_test
{

    class Program
    {
        static async Task Main(string[] args)
        {
      
      
            //int requestsPorSegundo = 1;
            //int duracionSegundos = 1; // tiempo total de la prueba

            //var sw = Stopwatch.StartNew();
            //int totalRequests = 0;

            //for (int segundo = 0; segundo < duracionSegundos; segundo++)
            //{
            //    var tareas = new List<Task>();

            //    for (int i = 0; i < requestsPorSegundo; i++)
            //    {
            //        tareas.Add(Task.Run(async () =>
            //        {
            //            //    var result = await CallApi($"{baseUrl}/lineas", apiKey, secretKey);
            //           // var result = await CallApi($"{baseUrl}/prediccion", apiKey, secretKey, new Dictionary<string, string> { { "fkparada", "5665" }, { "fklineaForzada", "255" } });

            //                   var result = await CallApi($"{baseUrl}/paradas-por-recorrido", apiKey, secretKey, new Dictionary<string, string> { { "recorrido", "26730" } });

            //            Interlocked.Increment(ref totalRequests);
            //            Console.WriteLine($"[{DateTime.Now:HH:mm:ss.fff}] Status: {result.StatusCode}");
            //        }));
            //    }

            //    await Task.WhenAll(tareas);

            //    //   Esperar hasta el siguiente segundo
            //    await Task.Delay(1000);
            //}

            //sw.Stop();
            //Console.WriteLine($"\nPrueba finalizada en {sw.Elapsed.TotalSeconds:N2} segundos");
            //Console.WriteLine($"Total de requests: {totalRequests}");

      
            //villa galicia
            string apiKey = "5f81c3a7d9be4f126ab8e47cd2f63a0e91b7c4d2";
            string secretKey = "c1e47ab92d5f83a6b74e2190fa6d3bc58e2a7f41";
 

            // string baseUrl = "http://localhost:5000/api/bondicom";
            //  string baseUrl = "http://vps-4507923-x.dattaweb.com:5000/api/bondicom";

            string baseUrl = "http://www.ojosauron.com.ar:5000/api/bondicom";

            // 1) Llamar a /lineas
            var resultLineas = await CallApi($"{baseUrl}/lineas", apiKey, secretKey);
            if (resultLineas.StatusCode == 200)
            {

               // var pos = await CallApi($"{baseUrl}/posicion-colectivo", apiKey, secretKey, new Dictionary<string, string> { { "colectivo", "11" } });


                Console.WriteLine("Lineas:");
                Console.WriteLine(resultLineas.Response);

                // Extraer primer ID (si es posible)
                var lineaValida = ObtenerPrimerIdDesdeJson(resultLineas.Response);

                if (!string.IsNullOrEmpty(lineaValida))
                {
                    // Llamar a /recorridos con línea válida
                  //  var resultRecorridos = await CallApi($"{baseUrl}/recorridos", apiKey, secretKey, new Dictionary<string, string> { { "linea", lineaValida } });

                  //  Console.WriteLine($"\nRecorridos status: {resultRecorridos.StatusCode}");
                   // Console.WriteLine($"Recorridos response:\n{resultRecorridos.Response}");

                    // Llamar a /paradas-por-recorrido con un recorrido ficticio
                   // string recorrido = "26735"; // reemplazá con valor real
//                    var resultParadas = await CallApi($"{baseUrl}/paradas-por-recorrido", apiKey, secretKey, new Dictionary<string, string> { { "recorrido", recorrido } });
                    var resultParadas = await CallApi($"{baseUrl}/paradas-por-tipo", apiKey, secretKey, new Dictionary<string, string> { { "linea", lineaValida }, { "tipo", "IDA" } });

                    //var resultParadas = await CallApi($"{baseUrl}/paradas", apiKey, secretKey, new Dictionary<string, string> { { "linea", lineaValida } });


                  //  var prediccion = await CallApi($"{baseUrl}/prediccion", apiKey, secretKey, new Dictionary<string, string> { { "fkparada", "6040" }, { "fklineaForzada", lineaValida }, { "idReco", recorrido } });
                    var prediccion = await CallApi($"{baseUrl}/prediccion-por-tipo", apiKey, secretKey, new Dictionary<string, string> { { "fkparada", "5672" }, { "fklinea", lineaValida }, { "tipo", "IDA" } });

                    //    var prediccion = await CallApi($"{baseUrl}/prediccion", apiKey, secretKey, new Dictionary<string, string> { { "fkparada", "5665" }, { "fklineaForzada", lineaValida } });

                    //var prediccion = await CallApi($"{baseUrl}/prediccion", apiKey, secretKey, new Dictionary<string, string> { { "fkparada", "5665" }, { "fklineaForzada", lineaValida }, { "idReco", "26731" } });


                    Console.WriteLine($"\nParadas status: {resultParadas.StatusCode}");
                    Console.WriteLine($"Paradas response:\n{resultParadas.Response}");
                }
            }
            else
            {
                Console.WriteLine("Error al obtener líneas.");
            }
        }

        static async Task<(int StatusCode, string Response)> CallApi(string url, string apiKey, string secretKey, Dictionary<string, string> queryParams = null)
        {
            long timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            string body = "";

            if (queryParams != null && queryParams.Count > 0)
            {
                var query = new FormUrlEncodedContent(queryParams).ReadAsStringAsync().Result;
                url += "?" + query;
            }

            string dataToSign = apiKey + timestamp + body;
            string signature = GenerateSignature(dataToSign, secretKey);

            using (var httpClient = new HttpClient())
            {
                httpClient.DefaultRequestHeaders.Add("X-Api-Key", apiKey);
                httpClient.DefaultRequestHeaders.Add("X-TIMESTAMP", timestamp.ToString());
                httpClient.DefaultRequestHeaders.Add("X-SIGNATURE", signature);

                var response = await httpClient.GetAsync(url);
                string responseBody = await response.Content.ReadAsStringAsync();
                return ((int)response.StatusCode, responseBody);
            }
        }

        static string GenerateSignature(string data, string secret)
        {
            var keyBytes = Encoding.UTF8.GetBytes(secret);
            var dataBytes = Encoding.UTF8.GetBytes(data);
            using (var hmac = new HMACSHA256(keyBytes))
            {
                var hash = hmac.ComputeHash(dataBytes);
                return BitConverter.ToString(hash).Replace("-", "").ToLower();
            }
        }

        static string ObtenerPrimerIdDesdeJson(string json)
        {
            try
            {
                var lista = System.Text.Json.JsonDocument.Parse(json).RootElement;
                if (lista.ValueKind == System.Text.Json.JsonValueKind.Array && lista.GetArrayLength() > 0)
                {
                    var idProp = lista[0].GetProperty("id"); // cambiar a "Id" si tu API lo devuelve así
                    return idProp.ToString();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error al parsear JSON: " + ex.Message);
            }
            return null;
        }
    }
}
