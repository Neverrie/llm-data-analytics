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
import com.example.llmdataanalyst.core.model.HealthResponse
import com.example.llmdataanalyst.core.model.UserPublic
import com.example.llmdataanalyst.core.model.WorkspaceResponse
import retrofit2.http.Path
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import okhttp3.ResponseBody
import retrofit2.Response

interface ApiService {
    @GET("api/health")
    suspend fun health(): HealthResponse

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

    @GET("api/artifacts")
    suspend fun artifacts(): ArtifactsResponse

    @GET("api/artifacts/{artifactId}")
    suspend fun getArtifact(@Path("artifactId") artifactId: String): ArtifactItem

    @GET("api/artifacts/{artifactId}/preview")
    suspend fun getArtifactPreview(@Path("artifactId") artifactId: String): Response<ResponseBody>
}
