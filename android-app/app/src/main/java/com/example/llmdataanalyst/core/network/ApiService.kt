package com.example.llmdataanalyst.core.network

import com.example.llmdataanalyst.core.model.ArtifactsResponse
import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.model.AuthLoginRequest
import com.example.llmdataanalyst.core.model.AuthResponse
import com.example.llmdataanalyst.core.model.ChatDetailResponse
import com.example.llmdataanalyst.core.model.ChatsResponse
import com.example.llmdataanalyst.core.model.ChatMessageCreateRequest
import com.example.llmdataanalyst.core.model.ChatMessageItem
import com.example.llmdataanalyst.core.model.CreateChatRequest
import com.example.llmdataanalyst.core.model.DatasetsResponse
import com.example.llmdataanalyst.core.model.DatasetItem
import com.example.llmdataanalyst.core.model.DatasetPreviewResponse
import com.example.llmdataanalyst.core.model.DatasetProfileResponse
import com.example.llmdataanalyst.core.model.HealthResponse
import com.example.llmdataanalyst.core.model.Lab2RunRequest
import com.example.llmdataanalyst.core.model.Lab3AskRequest
import com.example.llmdataanalyst.core.model.UserPublic
import com.example.llmdataanalyst.core.model.WorkspaceResponse
import kotlinx.serialization.json.JsonElement
import retrofit2.http.Path
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import okhttp3.ResponseBody
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.Part
import retrofit2.http.Query

interface ApiService {
    @GET("api/health")
    suspend fun health(): HealthResponse

    @GET("api/health")
    suspend fun healthRaw(): Response<ResponseBody>

    @POST("api/auth/login")
    suspend fun login(@Body request: AuthLoginRequest): AuthResponse

    @POST("api/auth/demo-login")
    suspend fun demoLogin(): AuthResponse

    @GET("api/auth/me")
    suspend fun me(): UserPublic

    @GET("api/workspace")
    suspend fun workspace(): WorkspaceResponse

    @GET("api/chats")
    suspend fun chats(): ChatsResponse

    @POST("api/chats")
    suspend fun createChat(@Body request: CreateChatRequest): com.example.llmdataanalyst.core.model.ChatItem

    @GET("api/chats/{chatId}")
    suspend fun getChat(@Path("chatId") chatId: String): ChatDetailResponse

    @POST("api/chats/{chatId}/messages")
    suspend fun sendChatMessage(
        @Path("chatId") chatId: String,
        @Body request: ChatMessageCreateRequest
    ): ChatMessageItem

    @GET("api/datasets")
    suspend fun datasets(): DatasetsResponse

    @Multipart
    @POST("api/datasets/upload")
    suspend fun uploadDataset(@Part file: MultipartBody.Part): DatasetItem

    @GET("api/datasets/{datasetId}/preview")
    suspend fun datasetPreview(
        @Path("datasetId") datasetId: String,
        @Query("limit") limit: Int = 20
    ): DatasetPreviewResponse

    @GET("api/datasets/{datasetId}/profile")
    suspend fun datasetProfile(@Path("datasetId") datasetId: String): DatasetProfileResponse

    @GET("api/artifacts")
    suspend fun artifacts(): ArtifactsResponse

    @GET("api/artifacts/{artifactId}")
    suspend fun getArtifact(@Path("artifactId") artifactId: String): ArtifactItem

    @GET("api/artifacts/{artifactId}/preview")
    suspend fun getArtifactPreview(@Path("artifactId") artifactId: String): Response<ResponseBody>

    @GET("api/artifacts/{artifactId}/download")
    suspend fun downloadArtifact(@Path("artifactId") artifactId: String): Response<ResponseBody>

    @GET("api/lab2/status")
    suspend fun lab2Status(): JsonElement

    @GET("api/lab2/sample-data")
    suspend fun lab2SampleData(): JsonElement

    @POST("api/lab2/run")
    suspend fun lab2Run(@Body request: Lab2RunRequest = Lab2RunRequest()): JsonElement

    @GET("api/lab2/result")
    suspend fun lab2Result(): JsonElement

    @GET("api/lab2/download")
    suspend fun lab2Download(): Response<ResponseBody>

    @POST("api/lab3/ask")
    suspend fun lab3Ask(@Body request: Lab3AskRequest): JsonElement

    @GET("api/lab3/result")
    suspend fun lab3Result(): JsonElement
}
